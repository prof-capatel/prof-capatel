"""
Unit & Integration Tests for Tenant Dashboard 3-Card Consolidation & Clickable Routing.
Validates:
1. 3 Consolidated Metric Cards in Dashboard HTML (Attendance Activity, Workforce & Shifts, Leaves & Approvals).
2. Direct Clickable Navigation Routing (/logs, /employees or /students, /leave-management or /nodes).
3. Preservation of all dynamic DOM IDs (#statPresentCount, #statCheckedOutCount, #statTotalStudents, #statShiftHours, #statTodayLeavesCount, #statPendingLeavesCount).
4. Real-time /api/v1/attendance/stats endpoint returns absent and leave counts.
5. Modular SaaS fallbacks for Basic edition (Devices card instead of Leaves).
"""
import os
import sys
from pathlib import Path
import unittest
from fastapi.testclient import TestClient

# Setup path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

# Ensure DLL path for Anaconda OpenSSL if needed
anaconda_bin = r"C:\ProgramData\Anaconda3\Library\bin"
if os.path.exists(anaconda_bin):
    try:
        os.add_dll_directory(anaconda_bin)
    except Exception:
        pass
    if anaconda_bin not in os.environ.get("PATH", ""):
        os.environ["PATH"] = anaconda_bin + os.pathsep + os.environ.get("PATH", "")

from src.database.session import init_db, get_db_context
from src.database.models import Tenant, User, Student
from src.server.app import app
from src.server.rbac_middleware import create_access_token


class TestDashboard3CardConsolidationAndRouting(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.client = TestClient(app)

    def test_01_corporate_dashboard_3card_consolidation(self):
        """Test Corporate tenant renders exactly 3 consolidated, clickable cards with correct routing."""
        with get_db_context() as db:
            retail = db.query(Tenant).filter(Tenant.slug == "the-retail-store").first()
            self.assertIsNotNone(retail)
            retail.subscription_plan = "PRO"
            retail.tenant_type = "corporate"
            db.commit()

            admin_user = db.query(User).filter(User.username == "admin_retail", User.tenant_id == retail.id).first()
            if not admin_user:
                admin_user = db.query(User).filter(User.tenant_id == retail.id).first()
            self.assertIsNotNone(admin_user)

            token = create_access_token(user_id=admin_user.id, role="TENANT_ADMIN", tenant_id=retail.id, username=admin_user.username)
            retail_id = str(retail.id)

        self.client.cookies.set("access_token", token)
        self.client.cookies.set("active_role", "TENANT_ADMIN")
        self.client.cookies.set("active_tenant_id", retail_id)

        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        html = res.text

        # 1. Grid container exists
        self.assertIn("dashboard-3card-grid", html)

        # 2. Card 1: Attendance Summary (Check-in + Check-out) routing to /logs
        self.assertIn('id="cardAttendanceSummary"', html)
        self.assertIn("stat-card-clickable", html)
        self.assertIn("window.location.href='/logs'", html)
        self.assertIn('id="statPresentCount"', html)
        self.assertIn('id="statCheckedOutCount"', html)
        self.assertIn("Checked-In", html)
        self.assertIn("Checked-Out", html)

        # 3. Card 2: Organization / Workforce & Shifts routing to /employees
        self.assertIn('id="cardOrganizationSummary"', html)
        self.assertIn("window.location.href='/employees'", html)
        self.assertIn('id="statTotalStudents"', html)
        self.assertIn('id="statShiftHours"', html)
        self.assertIn("Workforce & Shifts", html)
        self.assertIn("Shift Hours", html)

        # 4. Card 3: Leaves & Approvals routing to /leave-management
        self.assertIn('id="cardLeaveSummary"', html)
        self.assertIn("window.location.href='/leave-management'", html)
        self.assertIn('id="statTodayLeavesCount"', html)
        self.assertIn('id="statPendingLeavesCount"', html)
        self.assertIn("Leaves & Approvals", html)
        self.assertIn("On Leave Today", html)
        self.assertIn("Pending Approvals", html)

    def test_02_educational_dashboard_3card_routing(self):
        """Test Educational tenant routes Card 2 to /students and displays Cooldown Window."""
        with get_db_context() as db:
            edu_tenant = db.query(Tenant).filter(Tenant.tenant_type == "educational").first()
            if not edu_tenant:
                edu_tenant = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            self.assertIsNotNone(edu_tenant)
            edu_tenant.subscription_plan = "SMART"
            db.commit()

            admin_user = db.query(User).filter(User.tenant_id == edu_tenant.id, User.role == "TENANT_ADMIN").first()
            if not admin_user:
                admin_user = db.query(User).filter(User.username == "admin").first()
            self.assertIsNotNone(admin_user)

            token = create_access_token(user_id=admin_user.id, role="TENANT_ADMIN", tenant_id=edu_tenant.id, username=admin_user.username)
            tenant_id = str(edu_tenant.id)

        self.client.cookies.set("access_token", token)
        self.client.cookies.set("active_role", "TENANT_ADMIN")
        self.client.cookies.set("active_tenant_id", tenant_id)

        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        html = res.text

        # Educational tenant should route to /students
        self.assertIn('id="cardOrganizationSummary"', html)
        self.assertIn("window.location.href='/students'", html)
        self.assertIn('id="statCooldownWindow"', html)
        self.assertIn("Cooldown", html)

    def test_03_basic_edition_fallback_card(self):
        """Test Basic edition displays Devices Card routing to /nodes instead of Leave Card."""
        with get_db_context() as db:
            retail = db.query(Tenant).filter(Tenant.slug == "the-retail-store").first()
            retail.subscription_plan = "BASIC"
            db.commit()

            admin_user = db.query(User).filter(User.username == "admin_retail", User.tenant_id == retail.id).first()
            token = create_access_token(user_id=admin_user.id, role="TENANT_ADMIN", tenant_id=retail.id, username=admin_user.username)
            retail_id = str(retail.id)

        self.client.cookies.set("access_token", token)
        self.client.cookies.set("active_role", "TENANT_ADMIN")
        self.client.cookies.set("active_tenant_id", retail_id)

        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        html = res.text

        # Basic edition should render cardNodesSummary routing to /nodes
        self.assertIn('id="cardNodesSummary"', html)
        self.assertIn("window.location.href='/nodes'", html)
        self.assertIn("Devices & Stations", html)
        self.assertIn('id="statActiveNodes"', html)

        # Revert back to PRO
        with get_db_context() as db:
            retail = db.query(Tenant).filter(Tenant.slug == "the-retail-store").first()
            retail.subscription_plan = "PRO"
            db.commit()

    def test_04_attendance_stats_api_metrics(self):
        """Test /api/v1/attendance/stats returns present, checked out, absent, and leave counts."""
        with get_db_context() as db:
            retail = db.query(Tenant).filter(Tenant.slug == "the-retail-store").first()
            retail.subscription_plan = "PRO"
            db.commit()

            admin_user = db.query(User).filter(User.username == "admin_retail", User.tenant_id == retail.id).first()
            token = create_access_token(user_id=admin_user.id, role="TENANT_ADMIN", tenant_id=retail.id, username=admin_user.username)
            retail_id = str(retail.id)

        self.client.cookies.set("access_token", token)
        self.client.cookies.set("active_role", "TENANT_ADMIN")
        self.client.cookies.set("active_tenant_id", retail_id)

        res = self.client.get("/api/v1/attendance/stats")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("present_today", data)
        self.assertIn("checked_in_today", data)
        self.assertIn("checked_out_today", data)
        self.assertIn("absent_today", data)
        self.assertIn("today_leaves_count", data)
        self.assertIn("pending_leaves_count", data)
        self.assertIn("shift_hours_display", data)
        self.assertIn("total_students", data)

    def test_05_css_stylesheet_3card_and_clickable_rules(self):
        """Test dashboard.css contains 3-column stats-grid and stat-card-clickable hover styles."""
        css_path = BASE_DIR / "src" / "server" / "static" / "css" / "dashboard.css"
        self.assertTrue(css_path.exists())
        css_text = css_path.read_text(encoding="utf-8")

        self.assertIn(".stat-card-clickable", css_text)
        self.assertIn("cursor: pointer", css_text)
        self.assertIn("grid-template-columns: repeat(3, minmax(0, 1fr))", css_text)
        self.assertIn(".stat-split-row", css_text)
        self.assertIn(".stat-split-col", css_text)


if __name__ == "__main__":
    unittest.main()
