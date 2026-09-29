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

            # Assert role dropdown is removed for company admin and three links are omitted
            self.assertNotIn("Select Role", html, f"'Select Role' dropdown must not appear on company login /login/{slug}")
            self.assertIn('id="loginRole"', html)
            self.assertIn('value="TENANT_ADMIN"', html)
            self.assertNotIn("Back to Website", html, f"'Back to Website' must not appear on /login/{slug}")
            self.assertNotIn("Super Admin Gateway", html, f"'Super Admin Gateway' must not appear on /login/{slug}")
            self.assertNotIn("Direct Tenant Login Portals", html, f"'Direct Tenant Login Portals' must not appear on /login/{slug}")

            # Assert standard clean login components are present
            self.assertIn("loginUsername", html)
            self.assertIn("loginPassword", html)
            self.assertIn("Sign In to Portal", html)
            self.assertIn("Organization Admin Username", html, f"'Organization Admin Username' must appear on /login/{slug}")

    def test_02_global_login_removes_sandbox_and_retains_roles(self):
        """Verify that default global /login and /saas enforce CURIOSITY HUB text, new title, and Organization Admin Username."""
        for endpoint in ["/login", "/saas"]:
            res = self.client.get(endpoint)
            self.assertEqual(res.status_code, 200)
            html = res.text

            # Requirement 1: Replace Enterprise Platform Gateway with CURIOSITY HUB
            self.assertIn("CURIOSITY HUB", html)
            self.assertNotIn("Enterprise Platform Gateway", html)

            # Updated Requirement: Face Recognition Employee Management System and remove Multi-Tenant Biometric Attendance System
            self.assertIn("Face Recognition Employee Management System", html)
            self.assertNotIn("Multi-Tenant Biometric Attendance System", html)
            self.assertNotIn("Identity Control Hub", html)

            # Restrict to tenant admins and verify Organization Admin Username label
            self.assertNotIn("Select Role", html)
            self.assertIn('id="loginRole"', html)
            self.assertIn('value="TENANT_ADMIN"', html)
            self.assertIn("Organization Admin Username", html)

            # Cleanliness assertions
            self.assertNotIn("Demo Sandbox", html)
            self.assertNotIn("Quick-Login Demo Profiles", html)
            self.assertNotIn("quickProfilesGrid", html)
            self.assertNotIn("Back to Website", html)
            self.assertNotIn("Super Admin Gateway", html)
            self.assertNotIn("Direct Tenant Login Portals", html)

        # Confirm super admin page retains 'Back to Website'
        res_sa = self.client.get("/super-admin/login")
        self.assertEqual(res_sa.status_code, 200)
        self.assertIn("Back to Website", res_sa.text)

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

    def test_05_subheader_hud_removed_across_tenant_portal(self):
        """Verify that the layout wrapper subheader HUD (acronyms, page subtitle banners, tenant store labels) is removed across all admin pages."""
        admin_u = self.db.query(User).filter(User.role == "TENANT_ADMIN", User.is_active == True).first()
        tenant = self.db.query(Tenant).filter(Tenant.id == admin_u.tenant_id).first()
        tenant.subscription_plan = "PRO"
        self.db.commit()

        token = create_access_token(
            user_id=admin_u.id, role="TENANT_ADMIN", tenant_id=admin_u.tenant_id, username=admin_u.username
        )
        self.client.cookies.set("access_token", token)

        routes_to_test = [
            "/dashboard",
            "/employees",
            "/logs",
            "/payroll",
            "/leave-management",
            "/settings",
        ]

        for route in routes_to_test:
            res = self.client.get(route, follow_redirects=False)
            self.assertEqual(res.status_code, 200, f"Route {route} failed with status {res.status_code}")
            html = res.text

            # Layout acronym wrapper and subheader HUD must not be present
            self.assertNotIn("layout-acronym-wrapper", html, f"Layout acronym wrapper must be removed on {route}")
            self.assertNotIn("page-acronym-badge", html, f"Page acronym badge must be removed on {route}")
            self.assertNotIn("Live Operational Dashboard & Real-Time Biometric HUD", html)
            self.assertNotIn("Real-Time Biometric HUD", html)

            # Website landing button must not be present in topbar
            self.assertNotIn('title="View Landing Page"', html)
            self.assertNotIn('href="/?view=landing"', html)

            # Topbar cleanup: tenant-badge-box and user-profile-badge must not be present
            self.assertNotIn("tenant-badge-box", html, f"tenant-badge-box must not appear on {route}")
            self.assertNotIn("user-profile-badge", html, f"user-profile-badge must not appear on {route}")
            self.assertNotIn('id="topBarTagline">Face Attendance System', html)


if __name__ == "__main__":
    unittest.main()
