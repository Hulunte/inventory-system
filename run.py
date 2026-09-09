"""Development server. Do NOT use in production.

For production, use: python production.py
"""
import sys

print("WARNING: Running in development mode with debug=True.", file=sys.stderr)
print("For production, use: python production.py", file=sys.stderr)

from app import create_app

app = create_app()

if __name__ == "__main__":
    # Keep a single development process. The Werkzeug reloader can leave stale
    # child processes holding port 5000 on Windows, including children that
    # inherited a different DATABASE_URL from a test run.
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
