import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from fastapi.testclient import TestClient
from src.server.app import app
from src.database.session import get_db
from src.database.models import Tenant, User
from src.server.rbac_middleware import create_access_token

class TestCorporateSubheadersCleanup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db = next(get_db())

        cls.corp_tenant = cls.db.query(Tenant).filter(
            Tenant.tenant_type.in_(["corporate", "company", "enterprise"]),
            Tenant.is_active == True,
            Tenant.is_deleted == False
        ).first()
        assert cls.corp_tenant is not None, "Active corporate tenant required"

        cls.corp_admin = cls.db.query(User).filter(User.tenant_id == cls.corp_tenant.id, User.role == "TENANT_ADMIN").first()
        if not cls.corp_admin:
            cls.corp_admin = User(
                username=f"admin_test_{cls.corp_tenant.slug}",
                role="TENANT_ADMIN",
                tenant_id=cls.corp_tenant.id,
                is_active=True
            )
            cls.db.add(cls.corp_admin)
            cls.db.commit()
            cls.db.refresh(cls.corp_admin)

        token = create_access_token(
            user_id=cls.corp_admin.id, role="TENANT_ADMIN", tenant_id=cls.corp_tenant.id, username=cls.corp_admin.username
        )
        cls.client.cookies.set("access_token", token)

    def test_01_employees_page_subheader_removed(self):
        """Test /employees page removes grid title and enroll button card header for corporate tenants."""
        res = self.client.get("/employees")
        self.assertEqual(res.status_code, 200)
        html = res.text
        self.assertNotIn("Institutional Directory &amp; Profile Management", html.replace("&", "&amp;"))
        self.assertNotIn("Manage registered employees, team leads, and staff with department and role filters.", html)
        self.assertNotIn("Manage registered students, faculty, and administrative personnel with cascading dropdown filters.", html)
        self.assertIn("dirSearchInput", html)

    def test_02_logs_page_subheader_removed(self):
        """Test /logs page removes grid title while preserving action buttons."""
        res = self.client.get("/logs")
        self.assertEqual(res.status_code, 200)
        html = res.text
        self.assertNotIn("<h3>\n                <i class=\"fa-solid fa-clock-rotate-left\"", html)
        self.assertNotIn("Attendance Logs &amp; Audit Trail", html.replace("&", "&amp;"))
        self.assertIn("Manual check in/out", html)
        self.assertIn("Export CSV", html)
        self.assertIn("Export Excel", html)

    def test_03_analytics_page_subheader_removed(self):
        """Test /analytics page removes grid title while preserving export action buttons."""
        res = self.client.get("/analytics")
        self.assertEqual(res.status_code, 200)
        html = res.text
        self.assertNotIn("<h3>\n            <i class=\"fa-solid fa-chart-line\"", html)
        self.assertNotIn("Workforce Analytics &amp; Attendance Audit", html.replace("&", "&amp;"))
        self.assertIn("Compliance Excel", html)
        self.assertIn("Compliance CSV", html)
        self.assertIn("Manual check in/out", html)

    def test_04_payroll_page_subheader_removed(self):
        """Test /payroll page removes grid title while preserving payroll action buttons."""
        res = self.client.get("/payroll")
        self.assertEqual(res.status_code, 200)
        html = res.text
        self.assertNotIn("<h3>\n            <i class=\"fa-solid fa-money-bill-wave\"", html)
        self.assertNotIn("Corporate Payroll &amp; Wage Management", html.replace("&", "&amp;"))
        self.assertIn("Payroll Settings", html)
        self.assertIn("Export Excel", html)
        self.assertIn("Export CSV", html)

    def test_05_leave_management_page_subheader_removed(self):
        """Test /leave-management page removes grid title while preserving leave action buttons."""
        res = self.client.get("/leave-management")
        self.assertEqual(res.status_code, 200)
        html = res.text
        self.assertNotIn("<h2>\n                    <i class=\"fa-solid fa-calendar-days\"", html)
        self.assertNotIn("Leave Management &amp; Review Dashboard", html.replace("&", "&amp;"))
        self.assertIn("Leave Master Settings", html)
        self.assertIn("Refresh", html)

    def test_06_settings_page_subheader_removed(self):
        """Test /settings page preserves System Settings header as instructed."""
        res = self.client.get("/settings")
        self.assertEqual(res.status_code, 200)
        html = res.text
        self.assertIn("System Settings &amp; Institutional Branding", html.replace("&", "&amp;"))
        self.assertIn("Institutional Profile &amp; White-Labeling", html.replace("&", "&amp;"))

if __name__ == "__main__":
    unittest.main()
