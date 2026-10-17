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
        [python_cmd, "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "backend"],
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

    def safe_terminate(proc):
        if proc is None or proc.poll() is not None:
            return
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                proc.terminate()
                proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def handle_sigint(signum, frame):
        print("\n[*] Shutting down NeuroScope 3D servers...")
        safe_terminate(backend_proc)
        safe_terminate(frontend_proc)
        print("[*] Successfully terminated.")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

    try:
        while True:
            time.sleep(1)
            if backend_proc.poll() is not None:
                print(f"[!] Backend exited with code {backend_proc.returncode}.")
                safe_terminate(frontend_proc)
                break
            if frontend_proc.poll() is not None:
                print(f"[!] Frontend exited with code {frontend_proc.returncode}.")
                safe_terminate(backend_proc)
                break
    except KeyboardInterrupt:
        handle_sigint(None, None)


if __name__ == "__main__":
    main()
