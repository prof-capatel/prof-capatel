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

    def test_corporate_dashboard_hero_metrics_and_bottom_gateway(self):
        """Test that corporate dashboard places 4 metric cards in hero grid and gateway at bottom."""
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

        # 1. Verify Hero Metrics Grid is present
        self.assertIn("hero-metrics-grid", html)
        self.assertIn("hero-stat-card", html)

        # 2. Verify all 4 corporate metric IDs are present in hero
        self.assertIn('id="statPresentCount"', html)
        self.assertIn('id="statCheckedOutCount"', html)
        self.assertIn('id="statTotalStudents"', html)
        self.assertIn('id="statShiftHours"', html)

        # 3. Verify corporate terminology
        self.assertIn("Checked-In Today", html)
        self.assertIn("Checked-Out Today", html)
        self.assertIn("Total Enrolled Employees", html)
        self.assertIn("Standard Shift Hours", html)

        # 4. Verify Biometric Terminal Gateway is rendered
        self.assertIn("Biometric Terminal Gateway & System Hub", html)
        self.assertIn('id="dashPortalUrl"', html)
        self.assertIn('id="dashOnboardUrl"', html)

        # 5. Verify ordering: hero-metrics-grid occurs before liveFeedContainer, and liveFeedContainer occurs before Biometric Terminal Gateway
        idx_hero = html.find("hero-metrics-grid")
        idx_feed = html.find("liveFeedContainer")
        idx_gateway = html.find("Biometric Terminal Gateway & System Hub")

        self.assertNotEqual(idx_hero, -1)
        self.assertNotEqual(idx_feed, -1)
        self.assertNotEqual(idx_gateway, -1)
        self.assertLess(idx_hero, idx_feed, "Hero metrics grid must appear before the live recognition feed table")
        self.assertLess(idx_feed, idx_gateway, "Biometric terminal gateway must appear at the bottom below the live feed table")

    def test_educational_dashboard_hero_metrics_and_bottom_gateway(self):
        """Test that educational dashboard places its 4 metrics in hero grid and gateway at bottom."""
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

        self.assertIn("hero-metrics-grid", html)
        self.assertIn('id="statPresentCount"', html)
        self.assertIn('id="statTotalStudents"', html)
        self.assertIn('id="statAbsentCount"', html)
        self.assertIn('id="statCooldownWindow"', html)
        self.assertIn("Connected Ingestion Nodes & System Hub", html)

if __name__ == "__main__":
    unittest.main()
