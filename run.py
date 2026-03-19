"""CodeSnap — python run.py"""
import os
from pathlib import Path

# Load .env
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

if __name__ == "__main__":
    import uvicorn
    print("⚡ CodeSnap at http://127.0.0.1:8080")
    uvicorn.run("server:app", host="127.0.0.1", port=8080, reload=False)
