import unittest
import os
import re
from fastapi.testclient import TestClient
from src.server.app import app
from src.server.rbac_middleware import create_access_token

class TestTenantAdminMobileResponsiveness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    def test_css_responsive_breakpoints_exist(self):
        """Verify dashboard.css contains required responsive media query breakpoints."""
        css_path = os.path.join(self.base_dir, "src", "server", "static", "css", "dashboard.css")
        self.assertTrue(os.path.exists(css_path), "dashboard.css must exist")
        
        with open(css_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for tablet and mobile breakpoints
        self.assertTrue(re.search(r"@media\s*\(\s*max-width:\s*(1023px|1024px)\s*\)", content), "Missing tablet breakpoint")
        self.assertTrue(re.search(r"@media\s*\(\s*max-width:\s*768px\s*\)", content), "Missing 768px mobile breakpoint")
        self.assertTrue(re.search(r"@media\s*\(\s*max-width:\s*480px\s*\)", content), "Missing 480px smartphone breakpoint")

    def test_css_drawer_and_hamburger_classes(self):
        """Verify drawer, backdrop, hamburger, and mobile user section CSS classes."""
        css_path = os.path.join(self.base_dir, "src", "server", "static", "css", "dashboard.css")
        with open(css_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn(".sidebar-backdrop", content)
        self.assertIn(".sidebar-backdrop.active", content)
        self.assertIn(".btn-hamburger", content)
        self.assertIn(".sidebar-close-btn", content)
        self.assertIn(".sidebar-mobile-user-section", content)
        self.assertIn(".table-container", content)
        self.assertIn(".desktop-only", content)

    def test_base_template_drawer_and_topbar_structure(self):
        """Verify base.html contains drawer elements and mobile-responsive topbar classes."""
        tmpl_path = os.path.join(self.base_dir, "src", "server", "templates", "base.html")
        self.assertTrue(os.path.exists(tmpl_path), "base.html must exist")

        with open(tmpl_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("btnMobileNavToggle", content)
        self.assertIn("sidebarBackdrop", content)
        self.assertIn("sidebar-mobile-user-section", content)
        self.assertIn("desktop-only", content)
        self.assertIn("mobileAppThemeSelect", content)

    def test_dashboard_template_camera_dock_mobile_safety(self):
        """Verify dashboard.html camera card has mobile/touch docking safety check."""
        tmpl_path = os.path.join(self.base_dir, "src", "server", "templates", "dashboard.html")
        self.assertTrue(os.path.exists(tmpl_path), "dashboard.html must exist")

        with open(tmpl_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("isTouchOrMobile", content)
        self.assertIn("resetCameraCardDock", content)

    def test_tenant_admin_page_renders_successfully(self):
        """Verify tenant admin live dashboard and employees directory render with 200 OK."""
        from src.database.session import get_db_context
        from src.database.models import Tenant, User
        tenant_id = 1
        user_id = 1
        with get_db_context() as db:
            tenant = db.query(Tenant).filter(Tenant.slug == "pulin1").first()
            if not tenant:
                tenant = db.query(Tenant).filter(Tenant.tenant_type == "corporate").first()
            if tenant:
                tenant.subscription_plan = "PRO"
                db.commit()
                tenant_id = tenant.id
            user = db.query(User).filter(User.tenant_id == tenant_id, User.role == "TENANT_ADMIN").first()
            if user:
                user_id = user.id

        # Create token for tenant admin
        token = create_access_token(user_id=user_id, role="TENANT_ADMIN", tenant_id=tenant_id, username="admin")
        self.client.cookies.set("access_token", token)
        self.client.cookies.set("active_role", "TENANT_ADMIN")
        self.client.cookies.set("active_tenant_id", str(tenant_id))

        # 1. Live Dashboard
        res_dash = self.client.get("/")
        self.assertEqual(res_dash.status_code, 200)
        self.assertIn("btnMobileNavToggle", res_dash.text)

        # 2. Employees Directory
        res_emp = self.client.get("/employees")
        self.assertEqual(res_emp.status_code, 200)
        self.assertIn("table-container", res_emp.text)

        # 3. Payroll Management
        res_pay = self.client.get("/payroll")
        self.assertEqual(res_pay.status_code, 200)
        self.assertIn("table-container", res_pay.text)

        # 4. Leave Management
        res_leave = self.client.get("/leave-management")
        self.assertEqual(res_leave.status_code, 200)

        # 5. Settings
        res_settings = self.client.get("/settings")
        self.assertEqual(res_settings.status_code, 200)

if __name__ == "__main__":
    unittest.main()
