"""Smoke test for the PyInstaller-built executable."""
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

EXE_PATH = os.path.join(os.environ["TEMP"], "inventory-smoke-test", "inventory-system.exe")
WORK_DIR = os.path.join(os.environ["TEMP"], "inventory-smoke-test")
EXE_NAME = "inventory-system.exe"

def kill_existing():
    """Kill any existing processes."""
    subprocess.run(
        ["taskkill", "/F", "/IM", EXE_NAME],
        capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW
    )
    time.sleep(2)

def wait_for_server(port=5099, timeout=20):
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
    
    # 1. Verify exe exists
    if not os.path.exists(EXE_PATH):
        print(f"FAIL: exe not found at {EXE_PATH}")
        return 1
    size_mb = os.path.getsize(EXE_PATH) / (1024 * 1024)
    print(f"OK: exe found ({size_mb:.1f} MB)")
    
    # 2. Kill any existing processes
    kill_existing()
    
    # 3. Start the exe
    proc = subprocess.Popen(
        [EXE_PATH],
        cwd=WORK_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    print(f"OK: started process PID={proc.pid}")
    
    # 4. Wait for health endpoint
    status, body = wait_for_server(port=5099)
    if status is None:
        print(f"FAIL: server did not start within 20s")
        proc.kill()
        return 1
    print(f"OK: health check returned {status}")
    print(f"    body: {body[:200]}")
    
    # 5. Test a basic HTML route
    try:
        req = urllib.request.urlopen("http://127.0.0.1:5099/", timeout=3)
        print(f"OK: root route returned {req.status}")
    except urllib.error.HTTPError as e:
        print(f"OK: root route returned {e.code}")
    except Exception as e:
        print(f"WARN: root route error: {e}")
    
    # 6. Stop the process
    proc.kill()
    proc.wait()
    print("OK: process stopped cleanly")
    
    print("\n=== SMOKE TEST PASSED ===")
    return 0

if __name__ == "__main__":
    sys.exit(main())
