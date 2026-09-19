import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from fastapi.testclient import TestClient
from src.server.app import app
from src.database.session import get_db, Base, engine
from src.database.models import Tenant, SystemBranding, Student, AttendanceRecord, User
from src.server.rbac_middleware import create_access_token

class TestCorporateDashboardLayout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db = next(get_db())

    def test_corporate_dashboard_side_by_side_feed_and_metrics(self):
        """Test that corporate dashboard places camera and live recognition feed side-by-side in dash-hero-grid, with stats strip and bottom gateway."""
        # Find corporate tenant and admin
        corp_tenant = self.db.query(Tenant).filter(Tenant.tenant_type.in_(["corporate", "company", "enterprise"]), Tenant.is_active == True).first()
        self.assertIsNotNone(corp_tenant, "Must have at least one active corporate tenant")
        
        corp_admin = self.db.query(User).filter(User.tenant_id == corp_tenant.id, User.role == "TENANT_ADMIN").first()
        if not corp_admin:
            corp_admin = User(
                username=f"admin_{corp_tenant.slug}",
                role="TENANT_ADMIN",
                tenant_id=corp_tenant.id,
                is_active=True
            )
            self.db.add(corp_admin)
            self.db.commit()
            self.db.refresh(corp_admin)

        token = create_access_token(
            user_id=corp_admin.id, role="TENANT_ADMIN", tenant_id=corp_tenant.id, username=corp_admin.username
        )
        self.client.cookies.set("access_token", token)

        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        html = res.text

        # 1. Verify 4 corporate metric IDs are present
        self.assertIn('id="statPresentCount"', html)
        self.assertIn('id="statCheckedOutCount"', html)
        self.assertIn('id="statTotalStudents"', html)
        self.assertIn('id="statShiftHours"', html)

        # 2. Verify corporate terminology in metrics strip
        self.assertIn("Today's Attendance", html)
        self.assertIn("Checked-In", html)
        self.assertIn("Checked-Out", html)
        self.assertIn("Workforce & Shifts", html)
        self.assertIn("Enrolled Staff", html)
        self.assertIn("Shift Hours", html)

        # 3. Verify side-by-side hero command grid and live camera + recognition feed
        self.assertIn("dash-hero-grid", html)
        self.assertIn("inlineCameraCard", html)
        self.assertIn("Live Recognition Feed", html)
        self.assertIn('id="liveFeedContainer"', html)

        # 4. Verify Biometric Terminal Gateway is rendered at bottom and is collapsible/collapsed by default
        self.assertIn("Biometric Terminal Gateway & System Hub", html)
        self.assertIn('toggleBiometricGateway', html)
        self.assertIn('id="biometricGatewayBody"', html)
        self.assertIn('display: none', html)
        self.assertIn('id="dashPortalUrl"', html)
        self.assertIn('id="dashOnboardUrl"', html)

        # 5. Verify Manual check in/out modal is embedded on dashboard with proper title
        self.assertIn('id="manualOverrideModal"', html)
        self.assertIn('id="manualOverrideForm"', html)
        self.assertIn('id="overrideStudentSelect"', html)
        self.assertIn("Manual check in/out", html)

        # 6. Verify role subtitle 'TENANT ADMIN' is omitted for tenant admins
        self.assertNotIn("TENANT ADMIN", html)

        # 7. Verify visual ordering: stats strip before hero grid, and hero grid before Biometric Gateway
        idx_stats = html.find("stats-grid")
        idx_hero = html.find("dash-hero-grid")
        idx_gateway = html.find("Biometric Terminal Gateway & System Hub")

        self.assertNotEqual(idx_stats, -1)
        self.assertNotEqual(idx_hero, -1)
        self.assertNotEqual(idx_gateway, -1)
        self.assertLess(idx_stats, idx_hero, "KPI Stats grid must appear above hero feed grid")
        self.assertLess(idx_hero, idx_gateway, "Hero feed grid must appear before bottom gateway")

    def test_employee_directory_label_refinement(self):
        """Test that /employees page removes grid title and enroll employee card header for company tenants."""
        corp_tenant = self.db.query(Tenant).filter(Tenant.tenant_type.in_(["corporate", "company", "enterprise"]), Tenant.is_active == True).first()
        self.assertIsNotNone(corp_tenant, "Must have at least one active corporate tenant")

        corp_admin = self.db.query(User).filter(User.tenant_id == corp_tenant.id, User.role == "TENANT_ADMIN").first()
        token = create_access_token(
            user_id=corp_admin.id, role="TENANT_ADMIN", tenant_id=corp_tenant.id, username=corp_admin.username
        )
        self.client.cookies.set("access_token", token)

        res = self.client.get("/employees")
        self.assertEqual(res.status_code, 200)
        html = res.text

        # Verify grid title and enroll button are removed from the card header in corporate directory
        self.assertNotIn("<h3>\n                <i class=\"fa-solid fa-users-gear\"", html)
        self.assertNotIn("Corporate Directory & Employee Management", html)
        self.assertIn("dirSearchInput", html)

    def test_educational_dashboard_metrics_and_feed_grid(self):
        """Test that educational dashboard places its 4 metrics and feed grid properly."""
        edu_tenant = self.db.query(Tenant).filter(Tenant.tenant_type == "educational", Tenant.is_active == True).first()
        self.assertIsNotNone(edu_tenant, "Must have at least one active educational tenant")

        edu_admin = self.db.query(User).filter(User.tenant_id == edu_tenant.id, User.role == "TENANT_ADMIN").first()
        if not edu_admin:
            edu_admin = self.db.query(User).filter(User.role == "SUPER_ADMIN").first()

        token = create_access_token(
            user_id=edu_admin.id, role=edu_admin.role, tenant_id=edu_tenant.id, username=edu_admin.username
        )
        self.client.cookies.set("access_token", token)

        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        html = res.text

        self.assertIn('id="statPresentCount"', html)
        self.assertIn('id="statTotalStudents"', html)
        self.assertIn('id="statAbsentCount"', html)
        self.assertIn('id="statCooldownWindow"', html)
        self.assertIn("Connected Ingestion Nodes & System Hub", html)

if __name__ == "__main__":
    unittest.main()

