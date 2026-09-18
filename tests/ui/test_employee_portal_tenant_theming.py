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
