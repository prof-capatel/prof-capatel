"""
Unit & Integration Tests for:
1. Employee Portal RBAC & Session Isolation (Prevent auth bypass / privilege escalation).
2. Payslip Scoped Access Control (Tenant & Student boundary checks).
3. Dynamic Payslip Navigation ('Back to Employee Portal' vs 'Back to Payroll').
4. Page Visibility API & Window Focus Camera Lifecycle Management.
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

from datetime import date
from src.database.session import init_db, get_db_context
from src.database.models import Tenant, User, Student, PayrollBatch, PayrollPayslip
from src.server.app import app
from src.server.routes.api_employee_portal import create_employee_token
from src.server.rbac_middleware import create_access_token


from src.utils.auth_utils import hash_password

class TestEmployeeAuthAndCameraVisibility(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        with get_db_context() as db:
            # 1. Get or create test tenant
            cls.test_tenant = db.query(Tenant).filter(Tenant.slug == "test-corp-sec-audit").first()
            if not cls.test_tenant:
                cls.test_tenant = Tenant(
                    name="Test Security Corp",
                    slug="test-corp-sec-audit",
                    tenant_type="corporate",
                    is_active=True,
                )
                db.add(cls.test_tenant)
                db.commit()
                db.refresh(cls.test_tenant)

            cls.tenant_id = cls.test_tenant.id
            cls.tenant_slug = cls.test_tenant.slug

            # 2. Get or create test employees (Students)
            cls.emp1 = db.query(Student).filter(Student.roll_number == "EMP-AUDIT-001", Student.tenant_id == cls.tenant_id).first()
            if not cls.emp1:
                cls.emp1 = Student(
                    name="Alice Audit",
                    roll_number="EMP-AUDIT-001",
                    tenant_id=cls.tenant_id,
                    department="Engineering",
                    is_active=True,
                    monthly_base_salary=50000.0,
                )
                db.add(cls.emp1)
                db.commit()
                db.refresh(cls.emp1)

            cls.emp2 = db.query(Student).filter(Student.roll_number == "EMP-AUDIT-002", Student.tenant_id == cls.tenant_id).first()
            if not cls.emp2:
                cls.emp2 = Student(
                    name="Bob Audit",
                    roll_number="EMP-AUDIT-002",
                    tenant_id=cls.tenant_id,
                    department="Sales",
                    is_active=True,
                    monthly_base_salary=45000.0,
                )
                db.add(cls.emp2)
                db.commit()
                db.refresh(cls.emp2)

            cls.emp1_id = cls.emp1.id
            cls.emp2_id = cls.emp2.id

            # 3. Create batch & payslips
            cls.batch = db.query(PayrollBatch).filter(
                PayrollBatch.tenant_id == cls.tenant_id,
                PayrollBatch.period_month == 9,
                PayrollBatch.period_year == 2026,
            ).first()
            if not cls.batch:
                cls.batch = PayrollBatch(
                    tenant_id=cls.tenant_id,
                    batch_number="TEST-BATCH-2026-09",
                    period_month=9,
                    period_year=2026,
                    start_date=date(2026, 9, 1),
                    end_date=date(2026, 9, 30),
                    status="APPROVED",
                )
                db.add(cls.batch)
                db.commit()
                db.refresh(cls.batch)

            cls.batch_id = cls.batch.id

            cls.payslip1 = db.query(PayrollPayslip).filter(
                PayrollPayslip.student_id == cls.emp1_id,
                PayrollPayslip.period_month == 9,
                PayrollPayslip.period_year == 2026,
            ).first()
            if not cls.payslip1:
                cls.payslip1 = PayrollPayslip(
                    tenant_id=cls.tenant_id,
                    batch_id=cls.batch_id,
                    student_id=cls.emp1_id,
                    period_month=9,
                    period_year=2026,
                    calendar_days=30,
                    working_days=26.0,
                    present_days=26.0,
                    gross_earnings=50000.0,
                    net_salary=48000.0,
                    payment_status="PAID",
                )
                db.add(cls.payslip1)
                db.commit()
                db.refresh(cls.payslip1)

            cls.payslip2 = db.query(PayrollPayslip).filter(
                PayrollPayslip.student_id == cls.emp2_id,
                PayrollPayslip.period_month == 9,
                PayrollPayslip.period_year == 2026,
            ).first()
            if not cls.payslip2:
                cls.payslip2 = PayrollPayslip(
                    tenant_id=cls.tenant_id,
                    batch_id=cls.batch_id,
                    student_id=cls.emp2_id,
                    period_month=9,
                    period_year=2026,
                    calendar_days=30,
                    working_days=26.0,
                    present_days=25.0,
                    gross_earnings=45000.0,
                    net_salary=43000.0,
                    payment_status="PAID",
                )
                db.add(cls.payslip2)
                db.commit()
                db.refresh(cls.payslip2)

            cls.payslip1_id = cls.payslip1.id
            cls.payslip2_id = cls.payslip2.id

            # 4. Create admin user
            cls.admin_user = db.query(User).filter(User.username == "sec_audit_admin", User.tenant_id == cls.tenant_id).first()
            if not cls.admin_user:
                cls.admin_user = User(
                    username="sec_audit_admin",
                    email="sec_admin@testcorp.com",
                    full_name="Security Audit Admin",
                    password_hash=hash_password("admin123"),
                    role="TENANT_ADMIN",
                    tenant_id=cls.tenant_id,
                    is_active=True,
                )
                db.add(cls.admin_user)
                db.commit()
                db.refresh(cls.admin_user)

            cls.admin_id = cls.admin_user.id

        # Generate tokens
        cls.emp1_token = create_employee_token(cls.emp1_id, cls.tenant_id, "EMP-AUDIT-001", "Alice Audit")
        cls.emp2_token = create_employee_token(cls.emp2_id, cls.tenant_id, "EMP-AUDIT-002", "Bob Audit")
        cls.admin_token = create_access_token(
            user_id=cls.admin_id,
            role="TENANT_ADMIN",
            tenant_id=cls.tenant_id,
            username="sec_audit_admin",
        )

    @classmethod
    def tearDownClass(cls):
        # Clean up test records
        with get_db_context() as db:
            db.query(PayrollPayslip).filter(PayrollPayslip.id.in_([cls.payslip1_id, cls.payslip2_id])).delete(synchronize_session=False)
            db.query(PayrollBatch).filter(PayrollBatch.id == cls.batch_id).delete(synchronize_session=False)
            db.query(User).filter(User.id == cls.admin_id).delete(synchronize_session=False)
            db.query(Student).filter(Student.id.in_([cls.emp1_id, cls.emp2_id])).delete(synchronize_session=False)
            db.query(Tenant).filter(Tenant.id == cls.tenant_id).delete(synchronize_session=False)
            db.commit()

    def setUp(self):
        self.client = TestClient(app)

    # --------------------------------------------------------------------------
    # 1. Payslip View & Employee Navigation Tests
    # --------------------------------------------------------------------------
    def test_employee_payslip_renders_portal_wages_back_button(self):
        """Employee viewing own payslip must see 'Back to Employee Portal' linking to #wages tab."""
        cookies = {"emp_session_token": self.emp1_token}
        res = self.client.get(f"/payroll/payslip/{self.payslip1_id}", cookies=cookies)
        self.assertEqual(res.status_code, 200)
        html = res.text
        self.assertIn("Back to Employee Portal", html)
        self.assertIn(f"/employee/{self.tenant_slug}/dashboard#wages", html)
        self.assertNotIn('href="/payroll"', html)

    def test_employee_cannot_view_other_employee_payslip(self):
        """Employee attempting to view another employee's payslip must receive 403 Forbidden."""
        cookies = {"emp_session_token": self.emp1_token}
        # Emp1 tries to view Emp2's payslip
        res = self.client.get(f"/payroll/payslip/{self.payslip2_id}", cookies=cookies)
        self.assertEqual(res.status_code, 403)
        self.assertIn("You do not have permission", res.text)

    def test_admin_payslip_renders_admin_payroll_back_button(self):
        """Tenant Admin viewing a payslip must see 'Back to Payroll' linking to /payroll."""
        cookies = {
            "access_token": self.admin_token,
            "active_tenant_id": str(self.tenant_id),
            "active_role": "TENANT_ADMIN",
        }
        res = self.client.get(f"/payroll/payslip/{self.payslip1_id}", cookies=cookies)
        self.assertEqual(res.status_code, 200)
        html = res.text
        self.assertIn("Back to Payroll", html)
        self.assertIn('href="/payroll"', html)
        self.assertNotIn("#wages", html)

    # --------------------------------------------------------------------------
    # 2. RBAC & Employee Session Boundary Enforcement
    # --------------------------------------------------------------------------
    def test_employee_session_redirected_from_admin_views(self):
        """Active employee session accessing admin pages is redirected to employee portal dashboard."""
        cookies = {"emp_session_token": self.emp1_token}
        admin_routes = [
            "/",
            "/students",
            "/employees",
            "/enroll",
            "/logs",
            "/nodes",
            "/analytics",
            "/settings",
            "/payroll",
            "/leave-management",
            "/academic-management",
            "/teacher-portal",
        ]

        for route in admin_routes:
            res = self.client.get(route, cookies=cookies, follow_redirects=False)
            self.assertEqual(
                res.status_code,
                303,
                f"Route {route} did not redirect employee session (status: {res.status_code})",
            )
            expected_dest = f"/employee/{self.tenant_slug}/dashboard"
            self.assertIn(
                expected_dest,
                res.headers.get("location", ""),
                f"Route {route} redirected to {res.headers.get('location')} instead of {expected_dest}",
            )

    # --------------------------------------------------------------------------
    # 3. Page Visibility API & Camera Lifecycle Audit
    # --------------------------------------------------------------------------
    def test_employee_login_template_has_visibility_listeners(self):
        """Verify employee_login.html includes visibilitychange and blur/focus camera controls."""
        tmpl_path = BASE_DIR / "src" / "server" / "templates" / "employee_login.html"
        self.assertTrue(tmpl_path.exists())
        content = tmpl_path.read_text(encoding="utf-8")
        self.assertIn("visibilitychange", content)
        self.assertIn("stopCameraStream", content)
        self.assertIn("resumeCameraStream", content)
        self.assertIn('window.addEventListener("blur"', content)
        self.assertIn('window.addEventListener("focus"', content)

    def test_self_attendance_template_has_visibility_listeners(self):
        """Verify self_attendance.html includes visibilitychange and blur/focus camera controls."""
        tmpl_path = BASE_DIR / "src" / "server" / "templates" / "self_attendance.html"
        self.assertTrue(tmpl_path.exists())
        content = tmpl_path.read_text(encoding="utf-8")
        self.assertIn("visibilitychange", content)
        self.assertIn("stopCameraStream", content)
        self.assertIn("resumeCameraStream", content)

    def test_tenant_portal_login_template_has_visibility_listeners(self):
        """Verify tenant_portal_login.html includes visibilitychange and blur/focus camera controls."""
        tmpl_path = BASE_DIR / "src" / "server" / "templates" / "tenant_portal_login.html"
        self.assertTrue(tmpl_path.exists())
        content = tmpl_path.read_text(encoding="utf-8")
        self.assertIn("visibilitychange", content)
        self.assertIn("stopCameraStream", content)
        self.assertIn("resumeCameraStream", content)

    def test_mobile_capture_template_has_visibility_listeners(self):
        """Verify mobile_capture.html includes visibilitychange and blur/focus camera controls."""
        tmpl_path = BASE_DIR / "src" / "server" / "templates" / "mobile_capture.html"
        self.assertTrue(tmpl_path.exists())
        content = tmpl_path.read_text(encoding="utf-8")
        self.assertIn("visibilitychange", content)
        self.assertIn("stopCameraStream", content)
        self.assertIn("resumeCameraStream", content)

    def test_dashboard_template_has_visibility_listeners(self):
        """Verify dashboard.html includes lifecycle camera cleanup listeners (pagehide/beforeunload)."""
        tmpl_path = BASE_DIR / "src" / "server" / "templates" / "dashboard.html"
        self.assertTrue(tmpl_path.exists())
        content = tmpl_path.read_text(encoding="utf-8")
        self.assertIn("pagehide", content)
        self.assertIn("beforeunload", content)
        self.assertIn("stopContinuousCapture", content)

    def test_employee_portal_supports_url_hash_tab_routing(self):
        """Verify employee_portal.html parses window.location.hash for tab navigation (e.g. #wages)."""
        tmpl_path = BASE_DIR / "src" / "server" / "templates" / "employee_portal.html"
        self.assertTrue(tmpl_path.exists())
        content = tmpl_path.read_text(encoding="utf-8")
        self.assertIn("window.location.hash", content)
        self.assertIn("switchEmpTab", content)


if __name__ == "__main__":
    unittest.main()
