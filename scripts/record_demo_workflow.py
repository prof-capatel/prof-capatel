"""
Playwright Workflow Video Recording for Demo Tenant ('Demo Store')
Automates navigation to the tenant portal login, credential submission,
smooth dashboard showcase, and video capture recording.
"""

import os
import sys
import time
import shutil
import argparse
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("record_demo_workflow")


def record_demo_workflow(
    base_url: str = "https://curiosityhub.co.in/login/demo-store",
    username: str = "demostore",
    password: str = "123",
    output_dir: str = "videos",
    target_filename: str = "demo_store_workflow.webm",
    headless: bool = True,
):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    final_video_file = output_path / target_filename

    logger.info("================================================================")
    logger.info("  PLAYWRIGHT WORKFLOW VIDEO RECORDER - DEMO STORE TENANT")
    logger.info("================================================================")
    logger.info(f"Target URL       : {base_url}")
    logger.info(f"Login Username   : {username}")
    logger.info(f"Output Directory : {output_path.resolve()}")
    logger.info(f"Headless Mode    : {headless}")
    logger.info("================================================================")

    with sync_playwright() as p:
        logger.info("Launching Chromium browser...")
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--use-fake-ui-for-media-stream",
                "--use-fake-device-for-media-stream",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        context = browser.new_context(
            record_video_dir=str(output_path),
            record_video_size={"width": 1280, "height": 720},
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        )

        page = context.new_page()

        page.on("console", lambda msg: logger.info(f"[BROWSER CONSOLE] {msg.text}"))
        page.on("pageerror", lambda err: logger.error(f"[BROWSER ERROR] {err}"))
        page.on("response", lambda res: logger.info(f"[HTTP {res.status}] {res.url}") if "api/v1/auth" in res.url or res.status >= 400 else None)

        try:
            logger.info(f"Navigating to tenant login portal: {base_url}...")
            page.goto(base_url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(1000)

            # Check if password fallback toggle is present (corporate tenant portal)
            btn_toggle = page.locator("#btnTogglePassword")
            if btn_toggle.is_visible():
                logger.info("Clicking 'Switch to Password Sign In' button...")
                btn_toggle.click()
                page.wait_for_timeout(500)

            # Explicitly select TENANT_ADMIN role if dropdown exists
            role_select = page.locator("#loginRole")
            if role_select.is_visible():
                logger.info("Selecting 'TENANT_ADMIN' role...")
                role_select.select_option(value="TENANT_ADMIN")
                page.wait_for_timeout(300)

            # Fill in username and password
            logger.info(f"Filling credentials for '{username}'...")
            username_input = page.locator("#loginUsername")
            password_input = page.locator("#loginPassword")

            username_input.wait_for(state="visible", timeout=10000)
            username_input.fill(username)
            page.wait_for_timeout(400)

            password_input.wait_for(state="visible", timeout=10000)
            password_input.fill(password)
            page.wait_for_timeout(400)

            # Submit the login form
            logger.info("Submitting login form...")
            btn_submit = page.locator("#btnLogin")
            btn_submit.click()

            # Wait for authentication alert to appear
            logger.info("Waiting for authentication response...")
            alert_box = page.locator("#loginAlert")
            alert_box.wait_for(state="visible", timeout=10000)
            logger.info(f"Login alert text: {alert_box.inner_text()}")

            # Wait for redirection to dashboard (URL path '/')
            logger.info("Waiting for redirect to tenant dashboard...")
            page.wait_for_function("() => window.location.pathname === '/'", timeout=20000)
            page.wait_for_load_state("load", timeout=15000)
            page.wait_for_selector(".metric-card, #attendanceTableBody, #inlineCameraCard", timeout=15000)
            logger.info(f"Successfully landed on Tenant Dashboard! Current URL: {page.url}")

            # Wait for dashboard components to initialize
            page.wait_for_timeout(1500)

            # Showcase Dashboard - smooth scroll walkthrough (~6 seconds)
            logger.info("Beginning 6-second dashboard walkthrough recording...")

            # Scroll down slowly to show metric cards and live attendance tables
            for y in range(0, 650, 65):
                page.evaluate(f"window.scrollTo({{ top: {y}, behavior: 'smooth' }});")
                page.wait_for_timeout(300)

            page.wait_for_timeout(1000)

            # Scroll back up to the top
            for y in range(650, -1, -65):
                page.evaluate(f"window.scrollTo({{ top: {y}, behavior: 'smooth' }});")
                page.wait_for_timeout(300)

            # Pause briefly to showcase the complete dashboard view
            page.wait_for_timeout(1500)
            logger.info("Dashboard walkthrough completed.")

        except Exception as e:
            logger.error(f"Error during automated workflow execution: {e}")
            raise
        finally:
            # Capture video handle before closing page
            video = page.video
            page.close()
            context.close()
            browser.close()

            if video:
                raw_video_path = video.path()
                logger.info(f"Playwright raw video generated at: {raw_video_path}")

                if os.path.exists(raw_video_path):
                    shutil.copy(raw_video_path, str(final_video_file))
                    size_kb = os.path.getsize(str(final_video_file)) / 1024
                    logger.info("================================================================")
                    logger.info("  RECORDING COMPLETED SUCCESSFULLY")
                    logger.info("================================================================")
                    logger.info(f"Saved Video File : {final_video_file.resolve()}")
                    logger.info(f"File Size        : {size_kb:.1f} KB")
                    logger.info("================================================================")
                    return str(final_video_file.resolve())
            else:
                logger.warning("No video recording handle was generated.")
                return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Record Playwright browser video for Demo Store Tenant")
    parser.add_argument("--url", default="https://curiosityhub.co.in/login/demo-store", help="Target login URL")
    parser.add_argument("--username", default="demostore", help="Login username")
    parser.add_argument("--password", default="123", help="Login password")
    parser.add_argument("--output-dir", default="videos", help="Directory to store recordings")
    parser.add_argument("--output-file", default="demo_store_workflow.webm", help="Target video filename")
    parser.add_argument("--headed", action="store_true", help="Run browser in visible headed mode")

    args = parser.parse_args()

    record_demo_workflow(
        base_url=args.url,
        username=args.username,
        password=args.password,
        output_dir=args.output_dir,
        target_filename=args.output_file,
        headless=not args.headed,
    )
