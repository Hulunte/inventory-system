"""Development server. Do NOT use in production.

For production, use: python production.py
"""
import sys

print("WARNING: Running in development mode with debug=True.", file=sys.stderr)
print("For production, use: python production.py", file=sys.stderr)

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
