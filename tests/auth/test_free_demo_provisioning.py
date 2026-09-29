"""
Integration and Unit Tests for Self-Service Free Demo Provisioning & AWS SES SMTP Integration.
Validates OTP request/rate-limiting, automated 7-day Pro tenant creation, seeded masters,
welcome dispatch, authentication cookie delivery, and trial expiration lockout.
"""

import os
import sys
import time
from pathlib import Path
from datetime import timedelta
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from fastapi import HTTPException

# Setup path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

# Ensure DLL path for Anaconda OpenSSL if needed
anaconda_bin = r"C:\ProgramData\Anaconda3\Library\bin"
if os.path.exists(anaconda_bin):
    try:
        os.add_dll_directory(anaconda_bin)
    except Exception:
        pass
    if anaconda_bin not in os.environ.get("PATH", ""):
        os.environ["PATH"] = anaconda_bin + os.pathsep + os.environ.get("PATH", "")

from src.database.session import init_db, SessionLocal
from src.database.models import (
    Tenant,
    User,
    SystemBranding,
    WorkShift,
    CompanyLocation,
    Department,
    DesignationMaster,
    LeaveType,
    SalaryComponent,
    AuditLog,
)
from src.server.app import app
from src.server.routes.api_demo import _OTP_STORE, _RATE_LIMIT_STORE
from src.server.rbac_middleware import (
    check_tenant_login_access,
    check_tenant_operational_access,
)
from src.utils.timezone import get_ist_now


class TestFreeDemoProvisioning(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)
        cls.test_emails = [
            "demotester1@example.com",
            "demotester2@example.com",
            "demotester3@example.com",
            "demoratelimit@example.com",
        ]

    def setUp(self):
        # Clear rate limit and OTP memory stores for test isolation
        _OTP_STORE.clear()
        _RATE_LIMIT_STORE.clear()

    @classmethod
    def tearDownClass(cls):
        # Clean up any tenants created for test emails
        db = SessionLocal()
        try:
            test_tenants = (
                db.query(Tenant)
                .filter(
                    Tenant.contact_email.in_(cls.test_emails)
                    | Tenant.slug.like("acme-test-%")
                    | Tenant.slug.like("demo-%")
                )
                .all()
            )
            for t in test_tenants:
                db.delete(t)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    @patch("src.server.routes.api_demo.send_otp_email", return_value=True)
    def test_request_otp_validation_and_success(self, mock_send_email):
        """Test validation rules and successful OTP generation for Free Demo."""
        # 1. Invalid payload (missing company name)
        res_invalid = self.client.post(
            "/api/v1/demo/request-otp",
            json={
                "name": "Jane Tester",
                "mobile": "9876543210",
                "email": "demotester1@example.com",
            },
        )
        self.assertEqual(res_invalid.status_code, 422)

        # 2. Invalid email format
        res_bad_email = self.client.post(
            "/api/v1/demo/request-otp",
            json={
                "name": "Jane Tester",
                "company_name": "Acme Test Corp",
                "mobile": "9876543210",
                "email": "not-an-email",
            },
        )
        self.assertEqual(res_bad_email.status_code, 422)

        # 3. Valid request
        res_valid = self.client.post(
            "/api/v1/demo/request-otp",
            json={
                "name": "Jane Tester",
                "company_name": "Acme Test Corp",
                "mobile": "+91-9876543210",
                "email": "demotester1@example.com",
            },
        )
        self.assertEqual(res_valid.status_code, 200)
        data = res_valid.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("demotester1@example.com", data["message"])
        self.assertEqual(data["email"], "demotester1@example.com")

        # Verify OTP was registered in _OTP_STORE
        self.assertIn("demotester1@example.com", _OTP_STORE)
        stored = _OTP_STORE["demotester1@example.com"]
        self.assertEqual(stored["name"], "Jane Tester")
        self.assertEqual(stored["company_name"], "Acme Test Corp")
        self.assertEqual(stored["mobile"], "+91-9876543210")
        mock_send_email.assert_called_once()

    @patch("src.server.routes.api_demo.send_otp_email", return_value=True)
    def test_request_otp_rate_limiting(self, mock_send_email):
        """Verify that more than 3 OTP requests within the rate limit window trigger HTTP 429."""
        email = "demoratelimit@example.com"
        payload = {
            "name": "Spam Tester",
            "company_name": "Spam Corp",
            "mobile": "9998887776",
            "email": email,
        }

        # First 3 requests must succeed
        for i in range(3):
            res = self.client.post("/api/v1/demo/request-otp", json=payload)
            self.assertEqual(res.status_code, 200)

        # 4th request must be rejected with 429
        res_blocked = self.client.post("/api/v1/demo/request-otp", json=payload)
        self.assertEqual(res_blocked.status_code, 429)
        self.assertIn("Too many demo requests", res_blocked.json()["detail"])

    @patch("src.server.routes.api_demo.send_otp_email", return_value=True)
    def test_verify_otp_invalid_code_and_retry_limit(self, mock_send_email):
        """Verify handling of invalid OTP codes and attempt limits."""
        email = "demotester2@example.com"
        # Request OTP first
        self.client.post(
            "/api/v1/demo/request-otp",
            json={
                "name": "Bob Tester",
                "company_name": "Bob Tech Solutions",
                "mobile": "8887776665",
                "email": email,
            },
        )

        # Verify with wrong OTP
        res_fail = self.client.post(
            "/api/v1/demo/verify-and-provision",
            json={
                "email": email,
                "otp": "000000",
            },
        )
        self.assertEqual(res_fail.status_code, 400)
        self.assertIn("Invalid verification code", res_fail.json()["detail"])

        # Check attempt count incremented
        self.assertEqual(_OTP_STORE[email]["attempts"], 1)

    @patch("src.server.routes.api_demo.send_otp_email", return_value=True)
    @patch("src.server.routes.api_demo.send_demo_welcome_email", return_value=True)
    def test_verify_and_provision_full_tenant(self, mock_send_welcome, mock_send_otp):
        """
        Verify end-to-end self-service provisioning:
        - OTP verification
        - Corporate tenant creation on Pro edition
        - 7-day expiration timestamp
        - Seeded masters (shifts, locations, departments, designations, leaves, salary components)
        - Initial admin user creation
        - Authentication session cookies set
        - Direct redirect_url returned
        """
        email = "demotester3@example.com"
        # 1. Request OTP
        req_res = self.client.post(
            "/api/v1/demo/request-otp",
            json={
                "name": "Alice Wonder",
                "company_name": "Wonder Dynamics Ltd",
                "mobile": "9123456780",
                "email": email,
            },
        )
        self.assertEqual(req_res.status_code, 200)

        # Retrieve the generated OTP from mock or store
        # In our implementation, send_otp_email was called with otp_code
        call_args = mock_send_otp.call_args[1]
        otp_code = call_args["otp_code"]
        self.assertTrue(len(otp_code) == 6)

        # 2. Verify OTP and Provision Tenant
        verify_res = self.client.post(
            "/api/v1/demo/verify-and-provision",
            json={
                "email": email,
                "otp": otp_code,
            },
        )
        self.assertEqual(verify_res.status_code, 200)
        data = verify_res.json()

        self.assertEqual(data["status"], "success")
        self.assertEqual(data["redirect_url"], "/dashboard")
        self.assertEqual(data["tenant"]["edition"], "PRO")
        self.assertIn("Wonder Dynamics Ltd", data["tenant"]["name"])
        self.assertTrue(len(data["credentials"]["username"]) > 0)
        self.assertTrue(len(data["credentials"]["password"]) > 0)

        # 3. Check Session Cookies
        cookies = verify_res.cookies
        self.assertIn("access_token", cookies)
        self.assertIn("active_role", cookies)
        self.assertEqual(cookies.get("active_role"), "TENANT_ADMIN")
        self.assertIn("active_tenant_id", cookies)

        tenant_id = int(cookies.get("active_tenant_id"))

        # 4. Verify Database Integrity for New Tenant
        db = SessionLocal()
        try:
            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            self.assertIsNotNone(tenant)
            self.assertEqual(tenant.tenant_type, "corporate")
            self.assertEqual(tenant.subscription_plan, "PRO")
            self.assertEqual(tenant.subscription_status, "ACTIVE")
            self.assertIsNotNone(tenant.subscription_expires_at)

            # Ensure expiration is ~7 days in the future
            now_ist = get_ist_now()
            time_diff = tenant.subscription_expires_at - now_ist
            self.assertGreater(time_diff.total_seconds(), 6 * 86400)
            self.assertLessEqual(time_diff.total_seconds(), 8 * 86400)

            # Verify Branding
            branding = db.query(SystemBranding).filter(SystemBranding.tenant_id == tenant_id).first()
            self.assertIsNotNone(branding)
            self.assertEqual(tenant.saas_edition, "PRO")
            self.assertEqual(branding.header_badge_text, "Corporate Hub")

            # Verify Seeded Shifts (GEN, MORN, EVE)
            shifts = db.query(WorkShift).filter(WorkShift.tenant_id == tenant_id).all()
            self.assertGreaterEqual(len(shifts), 3)
            shift_codes = [s.code for s in shifts]
            self.assertIn("GEN", shift_codes)
            self.assertIn("MORN", shift_codes)
            self.assertIn("EVE", shift_codes)

            # Verify Seeded Branch Location
            locations = db.query(CompanyLocation).filter(CompanyLocation.tenant_id == tenant_id).all()
            self.assertGreaterEqual(len(locations), 1)
            self.assertEqual(locations[0].code, "HQ")

            # Verify Seeded Departments & Designations
            depts = db.query(Department).filter(Department.tenant_id == tenant_id).all()
            self.assertGreaterEqual(len(depts), 4)

            desigs = db.query(DesignationMaster).filter(DesignationMaster.tenant_id == tenant_id).all()
            self.assertGreaterEqual(len(desigs), 5)

            # Verify Seeded Leave Types & Salary Components
            leaves = db.query(LeaveType).filter(LeaveType.tenant_id == tenant_id).all()
            self.assertGreaterEqual(len(leaves), 4)

            salary_comps = db.query(SalaryComponent).filter(SalaryComponent.tenant_id == tenant_id).all()
            self.assertGreaterEqual(len(salary_comps), 5)

            # Verify Initial Admin User
            admin_user = (
                db.query(User)
                .filter(User.tenant_id == tenant_id, User.role == "TENANT_ADMIN")
                .first()
            )
            self.assertIsNotNone(admin_user)
            self.assertEqual(admin_user.email, email)
            self.assertEqual(admin_user.full_name, "Alice Wonder")

            # Verify Audit Log
            audit = (
                db.query(AuditLog)
                .filter(AuditLog.tenant_id == tenant_id, AuditLog.action_type == "DEMO_TENANT_PROVISIONED")
                .first()
            )
            self.assertIsNotNone(audit)
            self.assertIn("Self-service Free Demo provisioned", audit.description)

            # Verify welcome email was dispatched
            mock_send_welcome.assert_called_once()

        finally:
            db.close()

    def test_7_day_trial_expiration_lockout_enforcement(self):
        """
        Verify that rbac_middleware blocks expired tenants while permitting active trial tenants.
        """
        now = get_ist_now()

        # Mock Tenant with future expiration (Active trial)
        active_trial_tenant = Tenant(
            id=99901,
            name="Active Trial Org",
            slug="active-trial-org",
            subscription_status="ACTIVE",
            subscription_expires_at=now + timedelta(days=6),
            is_deleted=False,
        )

        # Login and operational access should NOT raise exception
        try:
            check_tenant_login_access(active_trial_tenant)
            check_tenant_operational_access(active_trial_tenant)
        except HTTPException:
            self.fail("check_tenant_login_access raised HTTPException on active trial tenant!")

        # Mock Tenant with past expiration (Expired trial)
        expired_trial_tenant = Tenant(
            id=99902,
            name="Expired Trial Org",
            slug="expired-trial-org",
            subscription_status="ACTIVE",
            subscription_expires_at=now - timedelta(hours=1),
            is_deleted=False,
        )

        # Login access must raise HTTP 403 Forbidden with Curiosity HUB upgrade message
        with self.assertRaises(HTTPException) as ctx_login:
            check_tenant_login_access(expired_trial_tenant)
        self.assertEqual(ctx_login.exception.status_code, 403)
        self.assertIn("EXPIRED", ctx_login.exception.detail)
        self.assertIn("Curiosity HUB", ctx_login.exception.detail)
        self.assertIn("+91-8866868245", ctx_login.exception.detail)

        # Operational access must raise HTTP 403 Forbidden
        with self.assertRaises(HTTPException) as ctx_op:
            check_tenant_operational_access(expired_trial_tenant)
        self.assertEqual(ctx_op.exception.status_code, 403)
        self.assertIn("EXPIRED", ctx_op.exception.detail)


if __name__ == "__main__":
    unittest.main()
