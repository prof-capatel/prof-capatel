import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from fastapi.testclient import TestClient
from src.server.app import app
from src.database.session import get_db
from src.database.models import Tenant, Student, SystemBranding
from src.server.routes.api_employee_portal import EMP_COOKIE_NAME, create_employee_token

class TestEmployeePortalTenantTheming(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db = next(get_db())

    def test_employee_login_page_renders_tenant_theme_and_clean_layout(self):
        """Verify /employee/{tenant_slug} renders clean tenant branding, dashboard.css, and theme selector."""
        corp_tenant = self.db.query(Tenant).filter(
            Tenant.tenant_type.in_(["corporate", "company", "enterprise"]),
            Tenant.is_active == True
        ).first()
        self.assertIsNotNone(corp_tenant, "Must have active corporate tenant")

        # Clear any existing cookies
        self.client.cookies.clear()

        res = self.client.get(f"/employee/{corp_tenant.slug}")
        self.assertEqual(res.status_code, 200)
        html = res.text

        # 1. Theme CSS and typography
        self.assertIn("/static/css/dashboard.css", html)
        self.assertIn("data-theme", html)
        self.assertIn("Plus Jakarta Sans", html)

        # 2. Branding header and theme toggle
        self.assertIn("portal-topbar", html)
        self.assertIn("themeToggleBtn", html)
        self.assertIn(corp_tenant.slug, html)

        # 3. Clean Face Login card and camera guide
        self.assertIn("login-card", html)
        self.assertIn("face-oval-guide", html)
        self.assertIn("btnScanFace", html)
        self.assertIn("HR Admin Login", html)

    def test_employee_portal_dashboard_renders_tenant_theme_and_tabs(self):
        """Verify /employee/{tenant_slug}/dashboard renders clean theme-aware profile card and 4 tabs."""
        # Find employee in corporate tenant
        corp_tenant = self.db.query(Tenant).filter(
            Tenant.tenant_type.in_(["corporate", "company", "enterprise"]),
            Tenant.is_active == True
        ).first()
        emp = self.db.query(Student).filter(Student.tenant_id == corp_tenant.id, Student.is_active == True).first()
        self.assertIsNotNone(emp, "Must have employee in corporate tenant")

        # Create valid employee token cookie
        token = create_employee_token(emp.id, corp_tenant.id, emp.roll_number, emp.name)
        self.client.cookies.set(EMP_COOKIE_NAME, token)

        res = self.client.get(f"/employee/{corp_tenant.slug}/dashboard")
        self.assertEqual(res.status_code, 200)
        html = res.text

        # 1. Theme CSS and typography
        self.assertIn("/static/css/dashboard.css", html)
        self.assertIn("data-theme", html)

        # 2. Header and Employee Profile card
        self.assertIn("portal-topbar", html)
        self.assertIn("emp-profile-card", html)
        self.assertIn(emp.name, html)
        self.assertIn(emp.roll_number, html)
        self.assertIn("themeToggleBtn", html)
        self.assertIn("Sign Out", html)

        # 3. 4 Clean Tabs
        self.assertIn('id="tabBtnPunches"', html)
        self.assertIn('id="tabBtnWages"', html)
        self.assertIn('id="tabBtnApply"', html)
        self.assertIn('id="tabBtnLeaves"', html)

        # 4. Clean cards and sections
        self.assertIn("clean-card", html)
        self.assertIn("Compensation & CTC Structure", html)
        self.assertIn("Submit Leave Application", html)
        self.assertIn("Annual Leave Quotas", html)

    def test_payslip_view_renders_theme_and_mobile_first_layout(self):
        """Verify /payroll/payslip/{id} dynamically inherits tenant theme and renders mobile-first layout."""
        # Find corporate tenant and student with payslip or create test fixture
        from src.database.models import PayrollPayslip, PayrollBatch
        from datetime import date

        corp_tenant = self.db.query(Tenant).filter(
            Tenant.tenant_type.in_(["corporate", "company", "enterprise"]),
            Tenant.is_active == True
        ).first()
        emp = self.db.query(Student).filter(Student.tenant_id == corp_tenant.id, Student.is_active == True).first()

        batch = self.db.query(PayrollBatch).filter(PayrollBatch.tenant_id == corp_tenant.id).first()
        if not batch:
            batch = PayrollBatch(
                tenant_id=corp_tenant.id,
                batch_number="TEST-THEME-BATCH",
                period_month=9,
                period_year=2026,
                start_date=date(2026, 9, 1),
                end_date=date(2026, 9, 30),
                status="APPROVED",
            )
            self.db.add(batch)
            self.db.commit()
            self.db.refresh(batch)

        payslip = self.db.query(PayrollPayslip).filter(PayrollPayslip.tenant_id == corp_tenant.id).first()
        if not payslip:
            payslip = PayrollPayslip(
                tenant_id=corp_tenant.id,
                batch_id=batch.id,
                student_id=emp.id,
                period_month=9,
                period_year=2026,
                calendar_days=30,
                working_days=26.0,
                present_days=26.0,
                gross_earnings=60000.0,
                net_salary=58000.0,
                payment_status="PAID",
            )
            self.db.add(payslip)
            self.db.commit()
            self.db.refresh(payslip)

        # Authenticate as employee
        token = create_employee_token(emp.id, corp_tenant.id, emp.roll_number, emp.name)
        self.client.cookies.set(EMP_COOKIE_NAME, token)

        res = self.client.get(f"/payroll/payslip/{payslip.id}")
        self.assertEqual(res.status_code, 200)
        html = res.text

        # 1. Theme CSS and data-theme
        self.assertIn("/static/css/dashboard.css", html)
        self.assertIn("data-theme", html)
        self.assertIn("themeToggleBtn", html)

        # 2. Mobile-first responsive tokens & sheet
        self.assertIn("payslip-sheet", html)
        self.assertIn("no-print-bar", html)
        self.assertIn("salary-breakdown", html)
        self.assertIn("net-pay-box", html)
        self.assertIn("details-grid", html)
        self.assertIn("attendance-bar", html)
        self.assertIn("@media (max-width: 640px)", html)

        # 3. Dynamic Back button
        self.assertIn("Back to Employee Portal", html)
        self.assertIn(f"/employee/{corp_tenant.slug}/dashboard#wages", html)

