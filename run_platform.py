"""
NeuroScope 3D - Single Command Platform Launcher
================================================
Launches the FastAPI backend and React Vite frontend concurrently.
Usage:
    python run_platform.py
"""
import sys
import os
import subprocess
import time
import signal

def main():
    print("=" * 70)
    print("NeuroScope 3D — Starting Full Web Application Platform")
    print("Research and teaching prototype only. Not for clinical diagnosis.")
    print("=" * 70)

    repo_root = os.path.dirname(os.path.abspath(__file__))
    frontend_dir = os.path.join(repo_root, "frontend")

    # Locate python in venv if available
    python_cmd = sys.executable
    venv_py = os.path.join(repo_root, ".venv", "Scripts", "python.exe")
    if not os.path.exists(venv_py):
        venv_py = os.path.join(repo_root, ".venv", "bin", "python")
    if os.path.exists(venv_py):
        python_cmd = venv_py

    print(f"[*] Python interpreter: {python_cmd}")
    print(f"[*] Starting FastAPI backend on http://127.0.0.1:8000 ...")

    backend_proc = subprocess.Popen(
        [python_cmd, "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
        cwd=repo_root
    )

    time.sleep(2)

    print(f"[*] Starting React Vite frontend on http://127.0.0.1:5173 ...")
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"

    frontend_proc = subprocess.Popen(
        [npm_cmd, "run", "dev"],
        cwd=frontend_dir
    )

    print("\n" + "=" * 70)
    print("[READY] NeuroScope 3D is running!")
    print("  - Web Frontend:  http://localhost:5173")
    print("  - Backend API:   http://localhost:8000")
    print("  - API Docs:      http://localhost:8000/docs")
    print("Press Ctrl+C to terminate both servers.")
    print("=" * 70 + "\n")

    def handle_sigint(signum, frame):
        print("\n[*] Shutting down NeuroScope 3D servers...")
        backend_proc.terminate()
        frontend_proc.terminate()
        backend_proc.wait()
        frontend_proc.wait()
        print("[*] Successfully terminated.")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

    try:
        while True:
            time.sleep(1)
            if backend_proc.poll() is not None:
                print("[!] Backend exited unexpectedly.")
                break
            if frontend_proc.poll() is not None:
                print("[!] Frontend exited unexpectedly.")
                break
    except KeyboardInterrupt:
        handle_sigint(None, None)


if __name__ == "__main__":
    main()
