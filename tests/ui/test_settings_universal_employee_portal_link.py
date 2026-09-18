import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from fastapi.testclient import TestClient
from src.server.app import app
from src.database.session import get_db
from src.database.models import Tenant, User
from src.server.rbac_middleware import create_access_token

class TestSettingsUniversalEmployeePortalLink(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db = next(get_db())

    def test_settings_security_tab_universal_employee_portal_link(self):
        """Test that Settings Attendance & Security tab renders Universal Employee Face-Login & Leave Portal card with clean URL, 1-click copy, and QR code."""
        # Find active corporate tenant and admin
        corp_tenant = self.db.query(Tenant).filter(
            Tenant.tenant_type.in_(["corporate", "company", "enterprise"]),
            Tenant.is_active == True
        ).first()
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

        res = self.client.get("/settings")
        self.assertEqual(res.status_code, 200)
        html = res.text

        # 1. Verify Tab 5 (Attendance & Security) pane
        self.assertIn('id="tabContentSecurity"', html)
        self.assertIn('id="tabBtnSecurity"', html)

        # 2. Verify Universal Employee Face-Login & Leave Portal Card
        self.assertIn("Universal Employee Face-Login & Leave Portal", html)
        self.assertIn("Mobile-First Portal", html)
        self.assertIn("1:N Facial Recognition", html)
        self.assertIn("Leave Balances", html)
        self.assertIn("Leave Applications", html)

        # 3. Verify clean URL span and Open Portal Button
        self.assertIn('id="universalEmployeePortalUrlSpan"', html)
        self.assertIn(f"/employee/{corp_tenant.slug}", html)
        self.assertIn('id="btnUniversalEmpPortalOpen"', html)
        self.assertIn(f'href="/employee/{corp_tenant.slug}"', html)

        # 4. Verify 1-click copy button and handler
        self.assertIn('onclick="copyUniversalEmployeePortalLink(this)"', html)
        self.assertIn("copyUniversalEmployeePortalLink", html)

        # 5. Verify Mobile QR Code integration
        self.assertIn('id="universalEmpPortalQrImg"', html)
        self.assertIn("https://api.qrserver.com/v1/create-qr-code/", html)
        self.assertIn("Instant Mobile QR", html)
