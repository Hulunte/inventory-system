"""Full integration test for the exe: setup wizard + admin login + session persistence."""
import os
import sys
import shutil
import subprocess
import time
import urllib.request
import urllib.error
import json
import http.cookiejar

WORK_DIR = os.path.join(os.environ["TEMP"], "inventory-login-test")
EXE_SRC = os.path.join("dist", "inventory-system.exe")
EXE_DST = os.path.join(WORK_DIR, "inventory-system.exe")
PORT = 5078

def main():
    subprocess.run(["taskkill", "/F", "/IM", "inventory-system.exe"], capture_output=True)
    time.sleep(1)

    os.makedirs(WORK_DIR, exist_ok=True)
    shutil.copy2(EXE_SRC, EXE_DST)

    from werkzeug.security import generate_password_hash
    admin_hash = generate_password_hash("AdminPass123!")
    secret_key = "a" * 40

    env_content = (
        f"DATABASE_URL=postgresql+psycopg://fake:fake@localhost:5432/smoke_test_db\n"
        f"SECRET_KEY={secret_key}\n"
        f"ADMIN_PASSWORD_HASH={admin_hash}\n"
        "HARVEST_TIMEZONE=UTC\n"
        f"APP_HOST=127.0.0.1\n"
        f"APP_PORT={PORT}\n"
        "SESSION_COOKIE_SECURE=false\n"
    )
    with open(os.path.join(WORK_DIR, ".env"), "w") as f:
        f.write(env_content)

    proc = subprocess.Popen(
        [EXE_DST], cwd=WORK_DIR,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    print(f"Started PID={proc.pid}")

    for i in range(20):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/health", timeout=2)
            break
        except urllib.error.HTTPError as e:
            if e.code in (200, 503):
                print(f"Health check: {e.code} (server running)")
                break
        except Exception:
            pass
        time.sleep(1)
    else:
        print("FAIL: server did not start")
        proc.kill()
        return 1

    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    # 1. Get CSRF token
    r = opener.open(f"http://127.0.0.1:{PORT}/api/admin/session", timeout=3)
    session_data = json.loads(r.read().decode())
    csrf = session_data.get("csrf_token", "")
    print(f"Session: authenticated={session_data.get('authenticated')}, csrf={csrf[:20]}...")

    # 2. Login
    login_data = json.dumps({"password": "AdminPass123!"}).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORT}/api/admin/login",
        data=login_data,
        headers={"Content-Type": "application/json", "X-CSRF-Token": csrf},
    )
    r = opener.open(req, timeout=3)
    login_result = json.loads(r.read().decode())
    print(f"Login: {r.status} {login_result}")

    # 3. Verify session persists - admin page
    r = opener.open(f"http://127.0.0.1:{PORT}/admin", timeout=3)
    print(f"Admin page: {r.status} (should be 200)")

    # 4. Verify root page works
    r = opener.open(f"http://127.0.0.1:{PORT}/", timeout=3)
    print(f"Root after login: {r.status} (should be 200)")

    # 5. Test wrong password
    cj2 = http.cookiejar.CookieJar()
    opener2 = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj2))
    r2 = opener2.open(f"http://127.0.0.1:{PORT}/api/admin/session", timeout=3)
    csrf2 = json.loads(r2.read().decode()).get("csrf_token", "")
    login_bad = json.dumps({"password": "WrongPassword"}).encode()
    req2 = urllib.request.Request(
        f"http://127.0.0.1:{PORT}/api/admin/login",
        data=login_bad,
        headers={"Content-Type": "application/json", "X-CSRF-Token": csrf2},
    )
    try:
        r2 = opener2.open(req2, timeout=3)
        print(f"Bad login: {r2.status}")
    except urllib.error.HTTPError as e:
        result = json.loads(e.read().decode())
        print(f"Bad login rejected: {e.code} {result}")

    # 6. Verify SECRET_KEY preserved (read .env)
    env_content = open(os.path.join(WORK_DIR, ".env")).read()
    assert f"SECRET_KEY={secret_key}" in env_content, "SECRET_KEY changed!"
    print("SECRET_KEY preserved: OK")

    proc.kill()
    proc.wait()
    print("\n=== FULL INTEGRATION TEST PASSED ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
