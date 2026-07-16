"""Build the web client and serve it to the Android emulator through FastAPI."""

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
BACKEND = ROOT / "backend"


def run() -> None:
    subprocess.run(["npm", "run", "build"], cwd=FRONTEND, check=True)
    subprocess.run(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd=BACKEND,
        check=True,
    )


if __name__ == "__main__":
    run()
