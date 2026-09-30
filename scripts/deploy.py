#!/usr/bin/env python3
"""
Curiosity HUB - Unified 1-Click Deployment Script
Handles:
1. Pre-flight hygiene (purge test records, run smoke tests)
2. Git commit & push to origin master
3. Remote EC2 synchronization & service restart via SSH
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
SSH_HOST = "16.171.10.243"
SSH_USER = "ubuntu"
SSH_KEY_CANDIDATES = [
    Path(os.path.expanduser(r"~/.ssh/Attendanceserver.pem")),
    Path(r"C:\Users\chirag\.ssh\Attendanceserver.pem"),
    Path(r"C:\Users\chirag\Downloads\Attendanceserver.pem"),
]

REMOTE_APP_DIR = "/home/ubuntu/attendance-system"
REMOTE_COMMANDS = (
    f"cd {REMOTE_APP_DIR} && "
    f"git pull origin master && "
    f"{REMOTE_APP_DIR}/venv/bin/python scripts/purge_test_records.py && "
    f"sudo systemctl restart attendance"
)


def get_ssh_key() -> Path:
    for key in SSH_KEY_CANDIDATES:
        if key.exists():
            return key
    raise FileNotFoundError(f"SSH Key not found in any of: {[str(k) for k in SSH_KEY_CANDIDATES]}")


def run_cmd(cmd, cwd=BASE_DIR, check=True):
    print(f"  [RUN] {cmd}")
    res = subprocess.run(cmd, cwd=str(cwd), shell=True, capture_output=True, text=True)
    if check and res.returncode != 0:
        print(f"  [ERROR] Command failed with code {res.returncode}:\n{res.stderr.strip()}")
        sys.exit(res.returncode)
    return res


def main():
    parser = argparse.ArgumentParser(description="Unified Git Push & EC2 Deployment Script")
    parser.add_argument("-m", "--message", default="", help="Git commit message")
    parser.add_argument("--skip-tests", action="store_true", help="Skip running pre-flight smoke tests")
    parser.add_argument("--no-push", action="store_true", help="Do not push git commits to remote repository")
    parser.add_argument("--no-deploy", action="store_true", help="Do not trigger remote EC2 deployment")
    parser.add_argument("--dry-run", action="store_true", help="Display actions without executing them")
    args = parser.parse_args()

    print("\n========================================================")
    print("  Curiosity HUB - Unified Push & Deploy Automation")
    print("========================================================\n")

    # Step 1: Pre-flight checks
    print("[1/4] Running pre-flight checks...")
    if args.dry_run:
        print("  [DRY-RUN] Would run purge_test_records.py and smoke tests")
    else:
        run_cmd(f'"{sys.executable}" scripts/purge_test_records.py')
        if not args.skip_tests:
            print("  Running fast smoke test suite...")
            run_cmd(f'"{sys.executable}" -m unittest tests.test_smoke')
        print("  [OK] Pre-flight checks passed.")

    # Step 2: Git status and commit
    print("\n[2/4] Checking Git repository status...")
    status_res = subprocess.run("git status --porcelain", cwd=str(BASE_DIR), shell=True, capture_output=True, text=True)
    has_changes = bool(status_res.stdout.strip())

    if has_changes:
        msg = args.message.strip() if args.message.strip() else "Update: codebase compacting, modular refactoring and optimizations"
        print(f"  Uncommitted changes detected. Committing with message:\n    \"{msg}\"")
        if args.dry_run:
            print("  [DRY-RUN] Would run: git add . && git commit -m ...")
        else:
            run_cmd("git add .")
            run_cmd(f'git commit -m "{msg}"')
            print("  [OK] Changes committed locally.")
    else:
        print("  Working tree is clean. No local commits required.")

    # Step 3: Git push
    if not args.no_push:
        print("\n[3/4] Pushing to GitHub (origin master)...")
        if args.dry_run:
            print("  [DRY-RUN] Would run: git push origin master")
        else:
            run_cmd("git push origin master")
            print("  [OK] Successfully pushed to origin master.")
    else:
        print("\n[3/4] Skipping git push (--no-push specified).")

    # Step 4: EC2 Deployment
    if not args.no_deploy and not args.no_push:
        print("\n[4/4] Deploying to AWS EC2 Production Server (16.171.10.243)...")
        ssh_key = get_ssh_key()
        ssh_cmd = (
            f'ssh -i "{ssh_key}" '
            f'-o StrictHostKeyChecking=no '
            f'-o ConnectTimeout=10 '
            f'{SSH_USER}@{SSH_HOST} "{REMOTE_COMMANDS}"'
        )
        if args.dry_run:
            print(f"  [DRY-RUN] Would run remote SSH: {ssh_cmd}")
        else:
            print(f"  Executing remote pull and reload via SSH (Key: {ssh_key.name})...")
            remote_res = run_cmd(ssh_cmd)
            print(f"  Remote output:\n{remote_res.stdout.strip()}")
            print("  [OK] Remote service restarted and synchronized.")
    else:
        print("\n[4/4] Skipping EC2 deployment.")

    print("\n========================================================")
    print("  Deployment Workflow Completed Successfully!")
    print("========================================================\n")


if __name__ == "__main__":
    main()
