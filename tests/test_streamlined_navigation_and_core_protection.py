import unittest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.server.app import app
from src.database.session import SessionLocal
from src.database.models import Tenant, User, Department, Student
from src.server.rbac_middleware import create_access_token
from scripts.purge_test_records import CORE_TENANT_SLUGS, CORE_USERNAMES
from scripts.cleanup_test_tenants import PRESERVED_TENANT_SPECS


class TestStreamlinedNavigationAndCoreProtection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db: Session = SessionLocal()

        # 1. Ensure educational tenant (Tenant #1)
        cls.edu_tenant = cls.db.query(Tenant).filter(Tenant.id == 1).first()
        if not cls.edu_tenant:
            cls.edu_tenant = Tenant(
                id=1,
                slug="default",
                name="Antigravity HQ Campus",
                tenant_type="educational",
                is_active=True,
            )
            cls.db.add(cls.edu_tenant)
            cls.db.commit()
            cls.db.refresh(cls.edu_tenant)

        # 2. Ensure corporate tenant (pulin1 / raymond-store-1)
        cls.corp_tenant = cls.db.query(Tenant).filter(Tenant.slug == "pulin1").first()
        if not cls.corp_tenant:
            cls.corp_tenant = cls.db.query(Tenant).filter(Tenant.tenant_type == "corporate").first()

        # 3. Create sample department for corporate tenant if needed
        if cls.corp_tenant:
            existing_dept = cls.db.query(Department).filter(Department.tenant_id == cls.corp_tenant.id).first()
            if not existing_dept:
                new_dept = Department(
                    tenant_id=cls.corp_tenant.id,
                    name="Retail Operations",
                    code="RETAIL",
                    description="Store inventory and floor operations",
                )
                cls.db.add(new_dept)
                cls.db.commit()

        # 4. Generate auth cookies
        # Corporate Admin
        cls.corp_user = cls.db.query(User).filter(User.tenant_id == cls.corp_tenant.id, User.role == "TENANT_ADMIN").first() if cls.corp_tenant else None
        if not cls.corp_user and cls.corp_tenant:
            cls.corp_user = User(
                tenant_id=cls.corp_tenant.id,
                username="test_corp_admin",
                email="corpadmin@test.com",
                password_hash="hash",
                role="TENANT_ADMIN",
                full_name="Corporate Administrator",
                is_active=True,
            )
            cls.db.add(cls.corp_user)
            cls.db.commit()
            cls.db.refresh(cls.corp_user)

        cls.corp_token = create_access_token(
            user_id=cls.corp_user.id,
            role="TENANT_ADMIN",
            tenant_id=cls.corp_tenant.id if cls.corp_tenant else 1,
            username=cls.corp_user.username,
        )

        # Educational Admin
        cls.edu_user = cls.db.query(User).filter(User.tenant_id == 1, User.role == "TENANT_ADMIN").first()
        cls.edu_token = create_access_token(
            user_id=cls.edu_user.id if cls.edu_user else 2,
            role="TENANT_ADMIN",
            tenant_id=1,
            username=cls.edu_user.username if cls.edu_user else "admin",
        )

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_corporate_sidebar_navigation_elements(self):
        """Verify corporate sidebar hides obsolete nodes, renames enrollment, and moves settings to bottom."""
        cookies = {
            "access_token": self.corp_token,
            "active_tenant_id": str(self.corp_tenant.id),
        }
        res = self.client.get("/", cookies=cookies)
        self.assertEqual(res.status_code, 200)
        html = res.text
        self.assertIn('<aside id="mainSidebar"', html)
        sidebar_html = html[html.find('<aside id="mainSidebar"'):html.find('</aside>')]

        # 1. Renamed enrollment link
        self.assertIn("Register New Employee", sidebar_html)
        self.assertIn("/enroll", sidebar_html)
        self.assertNotIn("Face Enrollment", sidebar_html)

        # 2. Obsolete nodes removed for corporate
        self.assertNotIn("Edge Nodes", sidebar_html)
        self.assertNotIn("Mobile Capture Node", sidebar_html)

        # 3. Standalone Departments & Teams removed from corporate sidebar
        self.assertNotIn('href="/departments"', sidebar_html)
        self.assertNotIn('href="/academic-management"', sidebar_html)

        # 4. Settings is present at bottom
        self.assertIn("Settings & Themes", sidebar_html)
        self.assertIn('href="/settings"', sidebar_html)

    def test_educational_sidebar_navigation_elements(self):
        """Verify educational sidebar retains academic classes, edge nodes, and standard enrollment label."""
        cookies = {
            "access_token": self.edu_token,
            "active_tenant_id": "1",
        }
        res = self.client.get("/", cookies=cookies)
        self.assertEqual(res.status_code, 200)
        html = res.text
        sidebar_html = html[html.find('<aside id="mainSidebar"'):html.find('</aside>')]

        self.assertIn("Face Enrollment", sidebar_html)
        self.assertIn("Academic & Classes", sidebar_html)
        self.assertIn("Edge Nodes", sidebar_html)

    def test_corporate_departments_redirect_to_settings(self):
        """Verify accessing /departments or /teams in corporate mode redirects to /settings#departmentsSection."""
        cookies = {
            "access_token": self.corp_token,
            "active_tenant_id": str(self.corp_tenant.id),
        }
        res_dept = self.client.get("/departments", cookies=cookies, follow_redirects=False)
        self.assertEqual(res_dept.status_code, 303)
        self.assertEqual(res_dept.headers.get("location"), "/settings#departmentsSection")

        res_teams = self.client.get("/teams", cookies=cookies, follow_redirects=False)
        self.assertEqual(res_teams.status_code, 303)
        self.assertEqual(res_teams.headers.get("location"), "/settings#departmentsSection")

    def test_settings_page_contains_departments_section(self):
        """Verify /settings renders the consolidated Departments & Teams management card."""
        cookies = {
            "access_token": self.corp_token,
            "active_tenant_id": str(self.corp_tenant.id),
        }
        res = self.client.get("/settings", cookies=cookies)
        self.assertEqual(res.status_code, 200)
        html = res.text

        self.assertIn('id="departmentsSection"', html)
        self.assertIn("Departments & Teams Management", html)
        self.assertIn("Add Department / Team", html)
        self.assertIn('id="deptModal"', html)

    def test_live_dashboard_attendance_capture_modal_and_button(self):
        """Verify live dashboard includes the Start Attendance Capture button and modal."""
        cookies = {
            "access_token": self.corp_token,
            "active_tenant_id": str(self.corp_tenant.id),
        }
        res = self.client.get("/", cookies=cookies)
        self.assertEqual(res.status_code, 200)
        html = res.text

        self.assertIn("Start Attendance Capture", html)
        self.assertIn('id="liveCaptureModal"', html)
        self.assertIn('id="captureVideo"', html)
        self.assertIn('id="captureCanvas"', html)
        self.assertIn('id="captureMatchToast"', html)

    def test_core_tenants_and_users_protection_constants(self):
        """Verify strict core entity protection lists include all 5 required tenants and core users."""
        expected_tenants = ["default", "pulin1", "ssec", "gecm", "raymond-store-1"]
        for t_slug in expected_tenants:
            self.assertIn(t_slug, CORE_TENANT_SLUGS, f"Missing {t_slug} in CORE_TENANT_SLUGS")

        preserved_slugs = [spec["slug"] for spec in PRESERVED_TENANT_SPECS if "slug" in spec]
        for t_slug in expected_tenants:
            self.assertIn(t_slug, preserved_slugs, f"Missing {t_slug} in PRESERVED_TENANT_SPECS")

        self.assertIn("raymond", CORE_USERNAMES)
        self.assertIn("superadmin", CORE_USERNAMES)
        self.assertIn("admin", CORE_USERNAMES)


if __name__ == "__main__":
    unittest.main()
