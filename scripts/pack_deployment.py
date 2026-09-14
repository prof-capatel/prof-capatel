"""
Local Deployment Packager:
Packs all necessary backend, frontend, database migration dumps, and assets
into a tar.gz bundle for SCP upload to EC2.
"""
import os
import tarfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "scratch"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TAR_PATH = OUTPUT_DIR / "attendance_deploy.tar.gz"

EXCLUDE_DIRS = {
    "venv",
    ".git",
    "__pycache__",
    ".pytest_cache",
    "graphify-out",
    "scratch",
}

EXCLUDE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".swp",
    ".tmp",
}


def should_exclude(tarinfo):
    path_parts = Path(tarinfo.name).parts
    for part in path_parts:
        if part in EXCLUDE_DIRS or part.startswith("."):
            return None
    ext = os.path.splitext(tarinfo.name)[1].lower()
    if ext in EXCLUDE_EXTENSIONS:
        return None
    return tarinfo


def main():
    print(f"[*] Packaging project from: {BASE_DIR}")
    print(f"[*] Destination archive   : {TAR_PATH}")

    if TAR_PATH.exists():
        TAR_PATH.unlink()

    with tarfile.open(TAR_PATH, "w:gz") as tar:
        # 1. Add core source directories
        for item in ["src", "scripts", "database", "data", "requirements.txt", "run_server.py", "run_enroll.py", "run_node.py", "README.md"]:
            src_path = BASE_DIR / item
            if src_path.exists():
                print(f"    [+] Adding {item}...")
                tar.add(src_path, arcname=item, filter=should_exclude)

    size_mb = TAR_PATH.stat().st_size / (1024 * 1024)
    print(f"[OK] Deployment archive created successfully: {size_mb:.2f} MB")


if __name__ == "__main__":
    main()
