"""
Unit & Integration Tests for Modular SaaS Editions (Basic, Smart, Pro),
Dashboard Leave Cards, and Dynamic Navigation & Feature Flag Gating.
"""
import os
import sys
from pathlib import Path
import unittest
from datetime import date, timedelta
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
from src.database.models import Tenant, User, Student, LeaveType, LeaveRequest
from src.server.app import app
from src.server.rbac_middleware import create_access_token
from src.server.routes.api_employee_portal import create_employee_token, EMP_COOKIE_NAME
from src.utils.timezone import get_ist_now


class TestModularSaasEditionsAndLeaveCards(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.client = TestClient(app)

    def test_01_tenant_model_edition_properties(self):
        """Test Tenant model SaaS edition normalization and feature flags."""
        tenant_basic = Tenant(name="Test Basic", slug="test-basic", subscription_plan="BASIC")
        self.assertEqual(tenant_basic.saas_edition, "BASIC")
        self.assertFalse(tenant_basic.has_leave_module)
        self.assertFalse(tenant_basic.has_payroll_module)

        tenant_free = Tenant(name="Test Free", slug="test-free", subscription_plan="FREE")
        self.assertEqual(tenant_free.saas_edition, "BASIC")
        self.assertFalse(tenant_free.has_leave_module)
        self.assertFalse(tenant_free.has_payroll_module)

        tenant_smart = Tenant(name="Test Smart", slug="test-smart", subscription_plan="SMART")
        self.assertEqual(tenant_smart.saas_edition, "SMART")
        self.assertTrue(tenant_smart.has_leave_module)
        self.assertFalse(tenant_smart.has_payroll_module)

        tenant_pro = Tenant(name="Test Pro", slug="test-pro", subscription_plan="PRO")
        self.assertEqual(tenant_pro.saas_edition, "PRO")
        self.assertTrue(tenant_pro.has_leave_module)
        self.assertTrue(tenant_pro.has_payroll_module)

        tenant_std = Tenant(name="Test Std", slug="test-std", subscription_plan="STANDARD")
        self.assertEqual(tenant_std.saas_edition, "PRO")
        self.assertTrue(tenant_std.has_leave_module)
        self.assertTrue(tenant_std.has_payroll_module)

    def test_02_dashboard_leave_cards_rendering_for_pro_tenant(self):
        """Test dashboard renders 'Today on Leave' and 'Pending Approvals' cards for Pro/Smart tenant."""
        with get_db_context() as db:
            retail = db.query(Tenant).filter(Tenant.slug == "the-retail-store").first()
            self.assertIsNotNone(retail)
            # Ensure Retail Store is on PRO edition
            retail.subscription_plan = "PRO"
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
        self.assertIn("On Leave Today", res.text)
        self.assertIn("Pending Approvals", res.text)
        self.assertIn("statTodayLeavesCount", res.text)
        self.assertIn("statPendingLeavesCount", res.text)

    def test_03_route_protection_payroll_on_smart_edition(self):
        """Test accessing /payroll on a SMART edition tenant redirects to dashboard with notice."""
        with get_db_context() as db:
            tenant = db.query(Tenant).filter(Tenant.slug == "the-retail-store").first()
            original_plan = tenant.subscription_plan
            tenant.subscription_plan = "SMART"
            db.commit()

            admin_user = db.query(User).filter(User.tenant_id == tenant.id).first()
            token = create_access_token(user_id=admin_user.id, role="TENANT_ADMIN", tenant_id=tenant.id, username=admin_user.username)
            tenant_id = str(tenant.id)

        try:
            self.client.cookies.set("access_token", token)
            self.client.cookies.set("active_role", "TENANT_ADMIN")
            self.client.cookies.set("active_tenant_id", tenant_id)

            res = self.client.get("/payroll", follow_redirects=False)
            self.assertEqual(res.status_code, 303)
            self.assertIn("notice=", res.headers["location"])
            self.assertIn("Payroll", res.headers["location"])
        finally:
            with get_db_context() as db:
                t = db.query(Tenant).filter(Tenant.slug == "the-retail-store").first()
                t.subscription_plan = original_plan
                db.commit()

    def test_04_route_protection_leave_management_on_basic_edition(self):
        """Test accessing /leave-management on a BASIC edition tenant redirects to dashboard with notice."""
        with get_db_context() as db:
            tenant = db.query(Tenant).filter(Tenant.slug == "the-retail-store").first()
            original_plan = tenant.subscription_plan
            tenant.subscription_plan = "BASIC"
            db.commit()

            admin_user = db.query(User).filter(User.tenant_id == tenant.id).first()
            token = create_access_token(user_id=admin_user.id, role="TENANT_ADMIN", tenant_id=tenant.id, username=admin_user.username)
            tenant_id = str(tenant.id)

        try:
            self.client.cookies.set("access_token", token)
            self.client.cookies.set("active_role", "TENANT_ADMIN")
            self.client.cookies.set("active_tenant_id", tenant_id)

            res = self.client.get("/leave-management", follow_redirects=False)
            self.assertEqual(res.status_code, 303)
            self.assertIn("notice=", res.headers["location"])
            self.assertIn("Leave", res.headers["location"])
        finally:
            with get_db_context() as db:
                t = db.query(Tenant).filter(Tenant.slug == "the-retail-store").first()
                t.subscription_plan = original_plan
                db.commit()

    def test_05_employee_portal_adaptive_subtabs(self):
        """Test employee portal dynamically adapts tabs (4 for Pro, 3 for Smart, 1 for Basic)."""
        with get_db_context() as db:
            tenant = db.query(Tenant).filter(Tenant.slug == "the-retail-store").first()
            student = db.query(Student).filter(Student.tenant_id == tenant.id, Student.is_active == True).first()
            self.assertIsNotNone(student)
            emp_token = create_employee_token(student_id=student.id, tenant_id=tenant.id, roll_number=student.roll_number, name=student.name)
            student_id = student.id
            tenant_id = tenant.id

        self.client.cookies.set(EMP_COOKIE_NAME, emp_token)

        # 1. Pro Edition -> 4 tabs (Punches, Wages, Apply Leave, My Quotas)
        with get_db_context() as db:
            t = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            t.subscription_plan = "PRO"
            db.commit()

        res_pro = self.client.get("/employee/the-retail-store/dashboard")
        self.assertEqual(res_pro.status_code, 200)
        self.assertIn("tabBtnPunches", res_pro.text)
        self.assertIn("tabBtnWages", res_pro.text)
        self.assertIn("tabBtnApply", res_pro.text)
        self.assertIn("tabBtnLeaves", res_pro.text)

        # 2. Smart Edition -> 3 tabs (Punches, Apply Leave, My Quotas - NO Wages)
        with get_db_context() as db:
            t = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            t.subscription_plan = "SMART"
            db.commit()

        res_smart = self.client.get("/employee/the-retail-store/dashboard")
        self.assertEqual(res_smart.status_code, 200)
        self.assertIn("tabBtnPunches", res_smart.text)
        self.assertNotIn("tabBtnWages", res_smart.text)
        self.assertIn("tabBtnApply", res_smart.text)
        self.assertIn("tabBtnLeaves", res_smart.text)

        # 3. Basic Edition -> 1 tab (Punches only)
        with get_db_context() as db:
            t = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            t.subscription_plan = "BASIC"
            db.commit()

        res_basic = self.client.get("/employee/the-retail-store/dashboard")
        self.assertEqual(res_basic.status_code, 200)
        self.assertIn("tabBtnPunches", res_basic.text)
        self.assertNotIn("tabBtnWages", res_basic.text)
        self.assertNotIn("tabBtnApply", res_basic.text)
        self.assertNotIn("tabBtnLeaves", res_basic.text)

        # Restore Pro
        with get_db_context() as db:
            t = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            t.subscription_plan = "PRO"
            db.commit()

    def test_06_employee_api_feature_gating_basic(self):
        """Test that employee API endpoints return 403 for gated modules on Basic tier."""
        with get_db_context() as db:
            tenant = db.query(Tenant).filter(Tenant.slug == "the-retail-store").first()
            student = db.query(Student).filter(Student.tenant_id == tenant.id, Student.is_active == True).first()
            emp_token = create_employee_token(student_id=student.id, tenant_id=tenant.id, roll_number=student.roll_number, name=student.name)
            tenant_id = tenant.id

            # Set to BASIC
            t = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            t.subscription_plan = "BASIC"
            db.commit()

        self.client.cookies.set(EMP_COOKIE_NAME, emp_token)

        try:
            # Payroll should return 403
            res_payroll = self.client.get("/api/v1/employee/payroll")
            self.assertEqual(res_payroll.status_code, 403)

            # Leave balances should return 403
            res_leave = self.client.get("/api/v1/employee/leave/balances")
            self.assertEqual(res_leave.status_code, 403)

            # Leave requests should return 403
            res_reqs = self.client.get("/api/v1/employee/leave/requests")
            self.assertEqual(res_reqs.status_code, 403)
        finally:
            with get_db_context() as db:
                t = db.query(Tenant).filter(Tenant.id == tenant_id).first()
                t.subscription_plan = "PRO"
                db.commit()


if __name__ == "__main__":
    unittest.main()
