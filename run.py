import subprocess
import sys
import os
import time

# C:\Users\USER\Downloads\ICMR_03-06-2026\ICMR_03-06-2026\ICMR_22_5_26
def run_servers():
    root_dir = os.path.dirname(os.path.abspath(__file__))

    # Auto-detect backend dir: wherever main.py lives
    possible_backends = [
        os.path.join(root_dir, "backend"),
        root_dir,  # fallback: everything in root
    ]
    backend_dir = None
    for p in possible_backends:
        if os.path.isfile(os.path.join(p, "main.py")):
            backend_dir = p
            break

    if not backend_dir:
        print("ERROR: Cannot find main.py in backend/ or root directory.")
        sys.exit(1)

    # Auto-detect frontend dir: wherever index.html lives
    possible_frontends = [
        os.path.join(root_dir, "frontend"),
        root_dir,
    ]
    frontend_dir = None
    for p in possible_frontends:
        if os.path.isfile(os.path.join(p, "index.html")):
            frontend_dir = p
            break

    if not frontend_dir:
        print("ERROR: Cannot find index.html in frontend/ or root directory.")
        sys.exit(1)

    print("Starting OCR Graph Application...")
    print(f"   Backend  dir : {backend_dir}")
    print(f"   Frontend dir : {frontend_dir}")

    # Use the venv python inside backend if it exists, else current python
    venv_python = os.path.join(backend_dir, "venv", "Scripts", "python.exe")  # Windows
    if not os.path.isfile(venv_python):
        venv_python = os.path.join(backend_dir, "venv", "bin", "python")  # Linux/Mac
    if not os.path.isfile(venv_python):
        venv_python = sys.executable  # fallback

    print(f"   Python       : {venv_python}")
    print()

    print("-> Starting FastAPI Backend on http://127.0.0.1:8000 ...")
    backend_cmd = [
        venv_python,
        "-m",
        "uvicorn",
        "main:app",
        "--reload",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
    ]
    backend_process = subprocess.Popen(backend_cmd, cwd=backend_dir, shell=False)

    time.sleep(3)

    print("-> Starting Frontend Server on http://localhost:4000 ...")
    frontend_cmd = [sys.executable, "-m", "http.server", "4000"]
    frontend_process = subprocess.Popen(frontend_cmd, cwd=frontend_dir, shell=False)

    print("\nBoth servers are running!")
    print("   Frontend : http://localhost:4000")
    print("   Backend  : http://127.0.0.1:8000")
    print("   API docs : http://127.0.0.1:8000/docs")
    print("\nPress Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping servers...")
        backend_process.terminate()
        frontend_process.terminate()
        backend_process.wait()
        frontend_process.wait()
        print("Servers stopped.")


if __name__ == "__main__":
    run_servers()
