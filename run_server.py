import argparse
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
from src.config import SERVER_HOST, SERVER_PORT, DATA_DIR


def get_local_ip() -> str:
    """Discovers the primary local LAN IPv4 address for Wi-Fi access."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"


def generate_self_signed_cert():
    """Generates a self-signed SSL cert/key for local HTTPS LAN testing."""
    ssl_dir = DATA_DIR / "ssl"
    ssl_dir.mkdir(parents=True, exist_ok=True)
    cert_path = ssl_dir / "cert.pem"
    key_path = ssl_dir / "key.pem"

    if not cert_path.exists() or not key_path.exists():
        try:
            from cryptography import x509
            from cryptography.x509.oid import NameOID
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization
            import datetime

            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, "FaceAttendance LAN Server"),
            ])
            cert = (
                x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(issuer)
                .public_key(key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(datetime.datetime.utcnow())
                .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
                .sign(key, hashes.SHA256())
            )

            with open(key_path, "wb") as f:
                f.write(key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption(),
                ))

            with open(cert_path, "wb") as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))

            print("[*] Generated self-signed SSL certificate for local HTTPS testing.")
        except Exception as e:
            print(f"[!] Note: SSL certificate generation requires cryptography package: {e}")
            return None, None

    return str(cert_path), str(key_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Central Attendance Server")
    parser.add_argument("--host", type=str, default=SERVER_HOST, help="Bind Host (0.0.0.0)")
    parser.add_argument("--port", type=int, default=SERVER_PORT, help="Port (8000)")
    parser.add_argument("--ssl", action="store_true", help="Enable HTTPS with self-signed SSL for mobile WebRTC")
    args = parser.parse_args()

    local_ip = get_local_ip()
    protocol = "https" if args.ssl else "http"

    print("================================================================")
    print("  THIN-CLIENT FACE RECOGNITION ATTENDANCE SERVER (CENTRAL HUB)  ")
    print("================================================================")
    print(f"[*] Dashboard URL    : {protocol}://localhost:{args.port}")
    print(f"[*] Local LAN URL    : {protocol}://{local_ip}:{args.port}")
    print(f"[*] Mobile Capture   : {protocol}://{local_ip}:{args.port}/mobile-capture")
    print(f"[*] Node Ingestion   : {protocol}://{local_ip}:{args.port}/api/v1/nodes/frame")
    print(f"[*] Interactive Docs : {protocol}://localhost:{args.port}/docs")
    print("================================================================\n")

    ssl_cert, ssl_key = None, None
    if args.ssl:
        ssl_cert, ssl_key = generate_self_signed_cert()

    uvicorn_kwargs = {
        "app": "src.server.app:app",
        "host": args.host,
        "port": args.port,
        "reload": True,
        "reload_dirs": [str(BASE_DIR / "src")],
        "access_log": True,
    }
    if ssl_cert and ssl_key:
        uvicorn_kwargs["ssl_certfile"] = ssl_cert
        uvicorn_kwargs["ssl_keyfile"] = ssl_key

    uvicorn.run(**uvicorn_kwargs)
