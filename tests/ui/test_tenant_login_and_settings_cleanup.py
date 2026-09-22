"""
Unit & Integration Tests for Tenant Login Sandbox Removal & Settings Text Refinement.
Validates:
1. Company tenant login pages (/login/{slug}) omit Demo Sandbox quick profiles and 'Filtered for' text.
2. Global /login retains demo profiles and role selectors.
3. Settings Tab 1 displays 'Institutional Profile'.
4. Settings Tab 5 displays 'Employee Portal', '(Share with Employees)', and removes obsolete badges.
"""
import sys
import os
from pathlib import Path
import unittest
from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.database.session import get_db, init_db
from src.database.models import Tenant, User
from src.server.app import app
from src.server.rbac_middleware import create_access_token


class TestTenantLoginAndSettingsCleanup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)
        cls.db = next(get_db())

    def test_01_company_tenant_login_no_sandbox_and_no_filter_text(self):
        """Verify that company tenant login pages remove Demo Sandbox and 'Filtered for' text."""
        # Test for corporate tenants
        for slug in ["the-retail-store", "ssec", "pulin1"]:
            res = self.client.get(f"/login/{slug}")
            self.assertEqual(res.status_code, 200, f"Failed for tenant slug: {slug}")
            html = res.text

            # Assert sandbox removal
            self.assertNotIn("Demo Sandbox", html, f"Demo Sandbox must not appear on /login/{slug}")
            self.assertNotIn("quickProfilesGrid", html, f"quickProfilesGrid must not appear on /login/{slug}")
            self.assertNotIn("Tenant Quick Profiles", html, f"Tenant Quick Profiles must not appear on /login/{slug}")

            # Assert 'Filtered for' banner removal
            self.assertNotIn("Filtered for", html, f"'Filtered for' banner must not appear on /login/{slug}")
            self.assertNotIn("roleBadgeHelp", html, f"roleBadgeHelp must not appear on /login/{slug}")

            # Assert standard clean login components are present
            self.assertIn("Select Role", html)
            self.assertIn("loginRole", html)
            self.assertIn("loginUsername", html)
            self.assertIn("loginPassword", html)
            self.assertIn("Sign In to Portal", html)

    def test_02_global_login_retains_sandbox_and_roles(self):
        """Verify that default global /login retains demo profile sandbox for global testing."""
        res = self.client.get("/login")
        self.assertEqual(res.status_code, 200)
        html = res.text

        self.assertIn("Demo Sandbox", html)
        self.assertIn("Quick-Login Demo Profiles", html)
        self.assertIn("quickProfilesGrid", html)
        self.assertIn("Super Administrator", html)
        self.assertIn("Tenant Administrator", html)

    def test_03_settings_tab1_institutional_profile_header(self):
        """Verify Settings Tab 1 header is renamed to 'Institutional Profile'."""
        admin_u = self.db.query(User).filter(User.role == "TENANT_ADMIN", User.is_active == True).first()
        self.assertIsNotNone(admin_u)

        token = create_access_token(
            user_id=admin_u.id, role="TENANT_ADMIN", tenant_id=admin_u.tenant_id, username=admin_u.username
        )
        self.client.cookies.set("access_token", token)

        res = self.client.get("/settings")
        self.assertEqual(res.status_code, 200)
        html = res.text

        self.assertIn("Institutional Profile", html)
        self.assertNotIn("Institutional Profile &amp; White-Labeling", html.replace("&", "&amp;"))
        self.assertNotIn("Institutional Profile & White-Labeling", html)

    def test_04_settings_tab5_employee_portal_text_refinements(self):
        """Verify Settings Tab 5 portal card title, link label, and badge cleanups."""
        admin_u = self.db.query(User).filter(User.role == "TENANT_ADMIN", User.is_active == True).first()
        token = create_access_token(
            user_id=admin_u.id, role="TENANT_ADMIN", tenant_id=admin_u.tenant_id, username=admin_u.username
        )
        self.client.cookies.set("access_token", token)

        res = self.client.get("/settings")
        self.assertEqual(res.status_code, 200)
        html = res.text

        # Header Title
        self.assertIn("Employee Portal", html)
        self.assertNotIn("Universal Employee Face-Login & Leave Portal", html)
        self.assertNotIn("Universal Employee Face-Login &amp; Leave Portal", html.replace("&", "&amp;"))

        # Badges removed
        self.assertNotIn("Mobile-First Portal", html)
        self.assertNotIn("1:N Facial Recognition", html)
        self.assertNotIn("Leave Balances", html)
        self.assertNotIn("Leave Applications", html)

        # Label refinement
        self.assertIn("Clean Employee Portal Link (Share with Employees)", html)
        self.assertNotIn("(Share with Workforce)", html)


if __name__ == "__main__":
    unittest.main()
