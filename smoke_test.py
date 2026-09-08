"""Smoke test for the PyInstaller-built executable."""
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.error

EXE_NAME = "inventory-system.exe"
SOURCE_EXE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist", EXE_NAME)
WORK_DIR = os.path.join(os.environ["TEMP"], "inventory-smoke-test")
EXE_PATH = os.path.join(WORK_DIR, EXE_NAME)
PORT = 5099

SMOKE_ENV = (
    "DATABASE_URL=postgresql+psycopg://fake:fake@localhost:5432/smoke_test_db\n"
    "SECRET_KEY=smoke-test-secret-key-that-is-long-enough-32chars!\n"
    "ADMIN_PASSWORD_HASH=pbkdf2:sha256:600000$smoke$salthash\n"
    "HARVEST_TIMEZONE=UTC\n"
    "APP_HOST=127.0.0.1\n"
    f"APP_PORT={PORT}\n"
)


def kill_existing():
    """Kill any existing processes."""
    subprocess.run(
        ["taskkill", "/F", "/IM", EXE_NAME],
        capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW
    )
    time.sleep(2)


def wait_for_server(port=PORT, timeout=20):
    """Wait for server to respond on health endpoint."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2)
            return req.status, req.read().decode()
        except urllib.error.HTTPError as e:
            if e.code in (503, 200):
                return e.code, e.read().decode()
        except Exception:
            pass
        time.sleep(1)
    return None, "timeout"


def main():
    print("=== Smoke Test: inventory-system.exe ===")

    # 1. Verify source exe exists
    if not os.path.exists(SOURCE_EXE):
        print(f"FAIL: source exe not found at {SOURCE_EXE}")
        return 1
    size_mb = os.path.getsize(SOURCE_EXE) / (1024 * 1024)
    print(f"OK: exe found ({size_mb:.1f} MB)")

    # 2. Kill any existing processes
    kill_existing()

    # 3. Create working directory and copy exe
    os.makedirs(WORK_DIR, exist_ok=True)
    shutil.copy2(SOURCE_EXE, EXE_PATH)
    print(f"OK: copied exe to {WORK_DIR}")

    # 4. Create .env
    env_path = os.path.join(WORK_DIR, ".env")
    with open(env_path, "w", encoding="utf-8") as f:
        f.write(SMOKE_ENV)
    print(f"OK: created .env")

    # 4. Start the exe
    proc = subprocess.Popen(
        [EXE_PATH],
        cwd=WORK_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    print(f"OK: started process PID={proc.pid}")

    # 5. Wait for health endpoint
    status, body = wait_for_server()
    if status is None:
        print(f"FAIL: server did not start within 20s")
        proc.kill()
        proc.wait()
        return 1
    print(f"OK: health check returned {status}")
    print(f"    body: {body[:200]}")

    # 6. Test the root route
    try:
        req = urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=3)
        print(f"OK: root route returned {req.status}")
    except urllib.error.HTTPError as e:
        print(f"OK: root route returned {e.code}")
    except Exception as e:
        print(f"WARN: root route error: {e}")

    # 7. Verify log file was created
    log_path = os.path.join(WORK_DIR, "logs", "inventory-system.log")
    if os.path.exists(log_path):
        print(f"OK: log file created at {log_path}")
    else:
        print(f"WARN: log file not found at {log_path}")

    # 8. Stop the process
    proc.kill()
    proc.wait()
    print("OK: process stopped cleanly")

    # Cleanup
    try:
        os.remove(env_path)
    except OSError:
        pass

    print("\n=== SMOKE TEST PASSED ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
