import os
import sys
from pathlib import Path

# Set working directory to project root
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Ensure DLL path for Anaconda OpenSSL if applicable
anaconda_bin = r"C:\ProgramData\Anaconda3\Library\bin"
if os.path.exists(anaconda_bin):
    try:
        os.add_dll_directory(anaconda_bin)
    except Exception:
        pass
    if anaconda_bin not in os.environ.get("PATH", ""):
        os.environ["PATH"] = anaconda_bin + os.pathsep + os.environ.get("PATH", "")

import socket
import uvicorn
from src.config import SERVER_HOST, SERVER_PORT


def get_local_ip() -> str:
    """Discovers the primary local LAN IPv4 address for Wi-Fi access."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        # Doesn't have to be reachable; used to route socket interface
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"


if __name__ == "__main__":
    local_ip = get_local_ip()

    print("================================================================")
    print("  THIN-CLIENT FACE RECOGNITION ATTENDANCE SERVER (CENTRAL HUB)  ")
    print("================================================================")
    print(f"[*] Dashboard URL    : http://localhost:{SERVER_PORT}")
    print(f"[*] Local LAN URL    : http://{local_ip}:{SERVER_PORT}")
    print(f"[*] Mobile Capture   : http://{local_ip}:{SERVER_PORT}/mobile-capture")
    print(f"[*] Node Ingestion   : http://{local_ip}:{SERVER_PORT}/api/v1/nodes/frame")
    print(f"[*] Interactive Docs : http://localhost:{SERVER_PORT}/docs")
    print("================================================================\n")

    uvicorn.run(
        "src.server.app:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=False,
        access_log=True,
    )
