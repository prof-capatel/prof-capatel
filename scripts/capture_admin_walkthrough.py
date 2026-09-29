"""
Sequential Playwright Screenshot Walkthrough for Demo Tenant Admin
Systematically navigates through every menu, tab, and modal in the admin portal
for the 'demo-store' tenant in proper sequence, capturing high-resolution screenshots.
"""

import os
import sys
import time
import argparse
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("capture_admin_walkthrough")


def capture_step(page, filename: Path, description: str, full_page: bool = True):
    """Helper to take a screenshot with descriptive logging."""
    logger.info(f"--> Capturing: {filename.name} ({description})")
    page.wait_for_timeout(800)  # Allow rendering & animation stabilization
    page.screenshot(path=str(filename), full_page=full_page)
    file_size_kb = os.path.getsize(str(filename)) / 1024
    logger.info(f"    Saved: {filename.name} [{file_size_kb:.1f} KB]")


def run_admin_walkthrough(
    base_url: str = "https://curiosityhub.co.in",
    tenant_slug: str = "demo-store",
    username: str = "demostore",
    password: str = "123",
    output_dir: str = "screenshots/walkthrough",
    headless: bool = True,
):
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("================================================================")
    logger.info("  PLAYWRIGHT SEQUENTIAL ADMIN SCREENSHOT WALKTHROUGH")
    logger.info("================================================================")
    logger.info(f"Portal Base URL  : {base_url}")
    logger.info(f"Tenant Slug      : {tenant_slug}")
    logger.info(f"Admin Username   : {username}")
    logger.info(f"Target Directory : {out_dir.resolve()}")
    logger.info("================================================================")

    login_url = f"{base_url.rstrip('/')}/login/{tenant_slug}"

    with sync_playwright() as p:
        logger.info("Launching Chromium browser (1920x1080 viewport)...")
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
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=1,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        )

        page = context.new_page()

        try:
            # -------------------------------------------------------------
            # STEP 01: Login Portal & Pre-filled Credentials
            # -------------------------------------------------------------
            logger.info("Step 1: Navigating to Tenant Login Portal...")
            page.goto(login_url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(1000)

            # Corporate toggle button check
            btn_toggle = page.locator("#btnTogglePassword")
            if btn_toggle.is_visible():
                btn_toggle.click()
                page.wait_for_timeout(400)

            role_select = page.locator("#loginRole")
            if role_select.is_visible():
                role_select.select_option(value="TENANT_ADMIN")
                page.wait_for_timeout(200)

            user_input = page.locator("#loginUsername")
            pass_input = page.locator("#loginPassword")

            user_input.wait_for(state="visible", timeout=10000)
            user_input.fill(username)
            pass_input.wait_for(state="visible", timeout=10000)
            pass_input.fill(password)
            page.wait_for_timeout(400)

            capture_step(page, out_dir / "01_login_portal.png", "Tenant Login Portal with credentials")

            # Submit login form
            logger.info("Submitting login form and authenticating...")
            btn_submit = page.locator("#btnLogin")
            btn_submit.click()

            page.wait_for_function("() => window.location.pathname === '/'", timeout=20000)
            page.wait_for_load_state("load", timeout=15000)
            page.wait_for_selector(".metric-card, #attendanceTableBody, #inlineCameraCard", timeout=15000)
            logger.info("Successfully authenticated and landed on Dashboard!")
            page.wait_for_timeout(1500)

            # -------------------------------------------------------------
            # STEP 02: Live Dashboard
            # -------------------------------------------------------------
            capture_step(page, out_dir / "02_dashboard_live.png", "Live Operational Dashboard")

            # -------------------------------------------------------------
            # STEP 03 & 04: Employee Directory & Edit Modal
            # -------------------------------------------------------------
            logger.info("Step 3: Navigating to Employee Directory (/employees)...")
            page.goto(f"{base_url.rstrip('/')}/employees", wait_until="load", timeout=30000)
            page.wait_for_timeout(1500)
            capture_step(page, out_dir / "03_employee_directory.png", "Employee Staff Directory")

            # Showcase Employee Edit Modal
            logger.info("Step 4: Opening Employee Edit Modal...")
            edit_btn = page.locator("button[onclick*='openEditModal'], .btn-secondary i.fa-pen-to-square").first
            if edit_btn.is_visible():
                edit_btn.click()
                page.wait_for_selector("#editStudentModal.active, #editStudentModal[style*='display: flex'], #editStudentModal", timeout=5000)
                page.wait_for_timeout(600)
                capture_step(page, out_dir / "04_employee_edit_modal.png", "Employee Profile Edit Modal with Salary Blueprint")
                # Close modal
                close_btn = page.locator("#editStudentModal .modal-close, #editStudentModal button:has-text('Cancel')").first
                if close_btn.is_visible():
                    close_btn.click()
                    page.wait_for_timeout(400)
            else:
                logger.warning("Edit button not found in Employee Directory; skipping modal screenshot.")

            # -------------------------------------------------------------
            # STEP 05: Register New Employee (Face Enrollment)
            # -------------------------------------------------------------
            logger.info("Step 5: Navigating to Register New Employee (/enroll)...")
            page.goto(f"{base_url.rstrip('/')}/enroll", wait_until="load", timeout=30000)
            page.wait_for_timeout(1500)
            capture_step(page, out_dir / "05_register_new_employee.png", "Register Employee & Biometric 3-Angle Enrollment")

            # -------------------------------------------------------------
            # STEP 06 & 07: Attendance Logs & Soft Delete Confirmation Modal
            # -------------------------------------------------------------
            logger.info("Step 6: Navigating to Attendance Logs (/logs)...")
            page.goto(f"{base_url.rstrip('/')}/logs", wait_until="load", timeout=30000)
            page.wait_for_timeout(1500)
            capture_step(page, out_dir / "06_attendance_logs_active.png", "Active Attendance Logs")

            # Showcase Soft Delete Modal
            logger.info("Step 7: Opening Attendance Soft Delete Modal...")
            del_btn = page.locator("button.btn-delete-log, button[onclick*='openDeleteAttendanceModal']").first
            if del_btn.is_visible():
                del_btn.click()
                page.wait_for_selector("#deleteAttendanceModal.active, #deleteAttendanceModal[style*='display: flex'], #deleteAttendanceModal", timeout=5000)
                page.wait_for_timeout(600)
                capture_step(page, out_dir / "07_attendance_logs_soft_delete_modal.png", "Soft Delete Attendance Confirmation Modal")
                # Close modal
                close_del_btn = page.locator("#deleteAttendanceModal .modal-close, #deleteAttendanceModal button:has-text('Cancel')").first
                if close_del_btn.is_visible():
                    close_del_btn.click()
                    page.wait_for_timeout(400)
            else:
                logger.warning("Delete log button not found in Attendance Logs; skipping modal screenshot.")

            # -------------------------------------------------------------
            # STEP 08: Analytics & Reports
            # -------------------------------------------------------------
            logger.info("Step 8: Navigating to Analytics & Reports (/analytics)...")
            page.goto(f"{base_url.rstrip('/')}/analytics", wait_until="load", timeout=30000)
            page.wait_for_timeout(1500)
            capture_step(page, out_dir / "08_analytics_and_reports.png", "Analytics & Defaulter Reports")

            # -------------------------------------------------------------
            # STEPS 09 - 13: Payroll Management & Sub-Tabs
            # -------------------------------------------------------------
            logger.info("Step 9: Navigating to Payroll Management (/payroll)...")
            page.goto(f"{base_url.rstrip('/')}/payroll", wait_until="load", timeout=30000)
            page.wait_for_timeout(1500)
            capture_step(page, out_dir / "09_payroll_monthly_batches.png", "Payroll Management - Monthly Batches Tab")

            # Sub-Tab: Employee Salary Structures
            tab_emp = page.locator("#tabBtnEmployees")
            if tab_emp.is_visible():
                logger.info("Step 10: Switching to Employee Salary Structures Tab...")
                tab_emp.click()
                page.wait_for_timeout(1000)
                capture_step(page, out_dir / "10_payroll_employee_structures.png", "Payroll - Employee Salary Structures Tab")

            # Sub-Tab: Salary Templates Master
            tab_tpl = page.locator("#tabBtnTemplates")
            if tab_tpl.is_visible():
                logger.info("Step 11: Switching to Salary Templates Master Tab...")
                tab_tpl.click()
                page.wait_for_timeout(1000)
                capture_step(page, out_dir / "11_payroll_salary_templates.png", "Payroll - Salary Templates Master Tab")

            # Sub-Tab: Payroll Masters
            tab_mas = page.locator("#tabBtnMasters")
            if tab_mas.is_visible():
                logger.info("Step 12: Switching to Payroll Masters Tab...")
                tab_mas.click()
                page.wait_for_timeout(1000)
                capture_step(page, out_dir / "12_payroll_masters.png", "Payroll - Component Masters Tab")

            # Sub-Tab: Attendance Wage Estimator
            tab_rt = page.locator("#tabBtnRealtime")
            if tab_rt.is_visible():
                logger.info("Step 13: Switching to Attendance Wage Estimator Tab...")
                tab_rt.click()
                page.wait_for_timeout(1000)
                capture_step(page, out_dir / "13_payroll_wage_estimator.png", "Payroll - Real-Time Wage Estimator Tab")

            # -------------------------------------------------------------
            # STEP 14: Leave Management
            # -------------------------------------------------------------
            logger.info("Step 14: Navigating to Leave Management (/leave-management)...")
            page.goto(f"{base_url.rstrip('/')}/leave-management", wait_until="load", timeout=30000)
            page.wait_for_timeout(1500)
            capture_step(page, out_dir / "14_leave_management.png", "Leave Management & Balances")

            # -------------------------------------------------------------
            # STEPS 15 - 21: Settings & Themes Sub-Tabs
            # -------------------------------------------------------------
            logger.info("Step 15: Navigating to Settings (/settings)...")
            page.goto(f"{base_url.rstrip('/')}/settings", wait_until="load", timeout=30000)
            page.wait_for_timeout(1500)
            capture_step(page, out_dir / "15_settings_organization_profile.png", "Settings - Organization Profile Tab")

            # Sub-Tab: Themes & Appearance
            tab_thm = page.locator("#tabBtnThemes")
            if tab_thm.is_visible():
                logger.info("Step 16: Switching to Themes & Appearance Tab...")
                tab_thm.click()
                page.wait_for_timeout(1000)
                capture_step(page, out_dir / "16_settings_themes_appearance.png", "Settings - Themes & Appearance Tab")

            # Sub-Tab: Departments
            tab_dept = page.locator("#tabBtnDepartments")
            if tab_dept.is_visible():
                logger.info("Step 17: Switching to Departments Tab...")
                tab_dept.click()
                page.wait_for_timeout(1000)
                capture_step(page, out_dir / "17_settings_departments.png", "Settings - Departments Management Tab")

            # Sub-Tab: Designations
            tab_desig = page.locator("#tabBtnDesignations")
            if tab_desig.is_visible():
                logger.info("Step 18: Switching to Designations Tab...")
                tab_desig.click()
                page.wait_for_timeout(1000)
                capture_step(page, out_dir / "18_settings_designations.png", "Settings - Designations & Role Masters Tab")

            # Sub-Tab: Shifts & Rules
            tab_shift = page.locator("#tabBtnShifts")
            if tab_shift.is_visible():
                logger.info("Step 19: Switching to Shifts & Rules Tab...")
                tab_shift.click()
                page.wait_for_timeout(1000)
                capture_step(page, out_dir / "19_settings_shifts_rules.png", "Settings - Shifts & Timings Tab")

            # Sub-Tab: Attendance & Security
            tab_sec = page.locator("#tabBtnSecurity")
            if tab_sec.is_visible():
                logger.info("Step 20: Switching to Attendance & Security Tab...")
                tab_sec.click()
                page.wait_for_timeout(1000)
                capture_step(page, out_dir / "20_settings_attendance_security.png", "Settings - Security & Thresholds Tab")

            # Sub-Tab: Geofencing & Portals
            tab_geo = page.locator("#tabBtnGeofencing")
            if tab_geo.is_visible():
                logger.info("Step 21: Switching to Geofencing & Portals Tab...")
                tab_geo.click()
                page.wait_for_timeout(1000)
                capture_step(page, out_dir / "21_settings_geofencing_portals.png", "Settings - Geofencing & Portal Access Tab")

            logger.info("================================================================")
            logger.info("  SCREENSHOT WALKTHROUGH COMPLETED SUCCESSFULLY")
            logger.info("================================================================")

        except Exception as e:
            logger.error(f"Error during walkthrough capture: {e}")
            raise
        finally:
            page.close()
            context.close()
            browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Capture sequential admin walkthrough screenshots")
    parser.add_argument("--base-url", default="https://curiosityhub.co.in", help="Platform base URL")
    parser.add_argument("--tenant", default="demo-store", help="Tenant slug")
    parser.add_argument("--username", default="demostore", help="Admin username")
    parser.add_argument("--password", default="123", help="Admin password")
    parser.add_argument("--output-dir", default="screenshots/walkthrough", help="Target screenshot directory")
    parser.add_argument("--headed", action="store_true", help="Run in visible headed mode")

    args = parser.parse_args()

    run_admin_walkthrough(
        base_url=args.base_url,
        tenant_slug=args.tenant,
        username=args.username,
        password=args.password,
        output_dir=args.output_dir,
        headless=not args.headed,
    )
