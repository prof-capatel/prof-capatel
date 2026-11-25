import unittest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.server.app import app
from src.database.session import SessionLocal, init_db
from src.database.models import (
    Tenant, Student, User, Department, DesignationMaster, WorkShift,
    AttendanceRecord, SystemBranding, CompanyLocation
)
from src.utils.auth_utils import verify_password, hash_password
from src.services.attendance_service import AttendanceService
from src.server.routes.api_demo import DemoVerifyRequest, _generate_clean_slug
from src.server.routes.api_demo import _OTP_STORE, verify_otp_and_provision
import time
from src.utils.timezone import get_ist_now


class TestCleanProvisionAndMultiPunchSequence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

    def setUp(self):
        self.db: Session = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_demo_provisioning_leaves_masters_empty(self):
        """Test that self-service demo tenant provisioning leaves departments, designations, and shifts empty."""
        test_email = "cleandemo_test@curiosityhub.co.in"
        test_company = "Clean Demo Industries"

        # Simulate OTP verified state in _OTP_STORE
        _OTP_STORE[test_email] = {
            "otp_hash": hash_password("999888"),
            "created_at": time.time(),
            "name": "Demo Admin",
            "company_name": test_company,
            "mobile": "9876500000",
            "attempts": 0,
        }

        res = self.client.post("/api/v1/demo/verify-and-provision", json={"email": test_email, "otp": "999888"})
        self.assertEqual(res.status_code, 200, f"Demo provisioning failed: {res.text}")
        data = res.json()
        self.assertEqual(data.get("status"), "success")

        tenant_id = data.get("tenant", {}).get("id")
        self.assertIsNotNone(tenant_id)
        self.db.commit()

        # Verify Departments are empty
        depts = self.db.query(Department).filter(Department.tenant_id == tenant_id).all()
        self.assertEqual(len(depts), 0, "Demo tenant departments must be empty by default.")

        # Verify Designations are empty
        desigs = self.db.query(DesignationMaster).filter(DesignationMaster.tenant_id == tenant_id).all()
        self.assertEqual(len(desigs), 0, "Demo tenant designations must be empty by default.")

        # Verify Work Shifts are empty
        shifts = self.db.query(WorkShift).filter(WorkShift.tenant_id == tenant_id).all()
        self.assertEqual(len(shifts), 0, "Demo tenant work shifts must be empty by default.")

        # Verify Primary location is preserved
        locs = self.db.query(CompanyLocation).filter(CompanyLocation.tenant_id == tenant_id).all()
        self.assertGreaterEqual(len(locs), 1, "Default primary location should remain preserved.")

    def test_onboard_registration_inactive_and_password(self):
        """Test mobile self-registration creates inactive status and provisioned inactive user credentials."""
        # Find or create a test corporate tenant
        tenant = self.db.query(Tenant).filter(Tenant.tenant_type == "corporate", Tenant.is_deleted == False).first()
        self.assertIsNotNone(tenant)

        test_roll = f"TEST-REG-{int(datetime.now().timestamp())}"
        test_pwd = "SecurePassword@123"

        payload = {
            "tenant_uuid": tenant.uuid or tenant.slug,
            "onboarding_token": tenant.onboarding_token,
            "name": "Self Registered Tester",
            "roll_number": test_roll,
            "password": test_pwd,
            "email": f"{test_roll.lower()}@testcorp.com",
            "role": "employee",
        }

        res = self.client.post("/api/v1/enroll/onboard/register", json=payload)
        self.assertEqual(res.status_code, 200, f"Onboard registration failed: {res.text}")
        data = res.json()
        self.assertEqual(data.get("status"), "success")

        self.db.commit()
        # Verify student profile in database
        student = self.db.query(Student).filter(Student.tenant_id == tenant.id, Student.roll_number == test_roll).first()
        self.assertIsNotNone(student)
        self.assertFalse(student.is_active, "Self-registered employee must be inactive by default.")
        self.assertEqual(student.employment_status, "INACTIVE", "Employment status must be INACTIVE by default.")

        # Verify associated User record
        user = self.db.query(User).filter(User.tenant_id == tenant.id, User.username == test_roll.lower()).first()
        self.assertIsNotNone(user, "User account should be provisioned from registration password.")
        self.assertFalse(user.is_active, "User account must remain inactive until admin approval.")
        self.assertTrue(verify_password(test_pwd, user.password_hash), "Password hash must verify accurately.")
        self.assertEqual(student.user_id, user.id)

        # Test Admin Approval activates both Student and User
        app_res = self.client.post(
            f"/api/v1/enroll/student/{student.id}/approve",
            headers={"X-Tenant-ID": str(tenant.id)}
        )
        self.assertEqual(app_res.status_code, 200)

        self.db.commit()
        student = self.db.query(Student).filter(Student.id == student.id).first()
        user = self.db.query(User).filter(User.id == user.id).first()
        self.assertTrue(student.is_active, "Student must be active after approval.")
        self.assertEqual(student.employment_status, "ACTIVE", "Employment status must be ACTIVE after approval.")
        self.assertTrue(user.is_active, "User account must be active after approval.")

    def test_multipunch_alternating_sequence_and_cooldown(self):
        """Test multi-punch check-in/out alternating sequence and absence of huge cooldown."""
        tenant = self.db.query(Tenant).filter(Tenant.tenant_id if hasattr(Tenant, 'tenant_id') else Tenant.id == 115).first()
        if not tenant:
            tenant = self.db.query(Tenant).filter(Tenant.tenant_type == "corporate", Tenant.is_deleted == False).first()

        # Clean existing test attendance for test student
        test_roll = f"EMP-MULTI-{int(datetime.now().timestamp()) % 100000}"
        student = Student(
            tenant_id=tenant.id,
            roll_number=test_roll,
            name="Multi Punch Employee",
            user_role="employee",
            is_active=True,
            employment_status="ACTIVE",
        )
        self.db.add(student)
        self.db.commit()
        self.db.refresh(student)

        service = AttendanceService(self.db)

        # Step 1: Attempt Check-Out without active Check-In -> Must fail with 400
        with self.assertRaises(Exception) as cm:
            service.record_punch(
                tenant_id=tenant.id,
                student_id=student.id,
                node_id="MOBILE-APP",
                punch_type="CHECK_OUT",
                is_self_attendance=False,
            )
        self.assertIn("400", str(cm.exception))

        # Step 2: Check-In (Cycle 1) -> Must succeed
        p1 = service.record_punch(
            tenant_id=tenant.id,
            student_id=student.id,
            node_id="MOBILE-APP",
            punch_type="CHECK_IN",
            is_self_attendance=False,
        )
        self.assertTrue(p1.get("attendance_logged"))
        self.assertEqual(p1.get("punch_type"), "CHECK_IN")

        # Step 3: Attempt duplicate Check-In while checked in -> Must fail with 400
        with self.assertRaises(Exception) as cm2:
            service.record_punch(
                tenant_id=tenant.id,
                student_id=student.id,
                node_id="MOBILE-APP",
                punch_type="CHECK_IN",
                is_self_attendance=False,
            )
        self.assertIn("400", str(cm2.exception))

        # Step 4: Check-Out (Cycle 1) -> Must succeed
        p2 = service.record_punch(
            tenant_id=tenant.id,
            student_id=student.id,
            node_id="MOBILE-APP",
            punch_type="CHECK_OUT",
            is_self_attendance=False,
        )
        self.assertTrue(p2.get("attendance_logged"))
        self.assertEqual(p2.get("punch_type"), "CHECK_OUT")

        # Step 5: Check-In (Cycle 2) -> Must succeed without 45114 min cooldown!
        p3 = service.record_punch(
            tenant_id=tenant.id,
            student_id=student.id,
            node_id="MOBILE-APP",
            punch_type="CHECK_IN",
            is_self_attendance=False,
        )
        self.assertTrue(p3.get("attendance_logged"))
        self.assertEqual(p3.get("punch_type"), "CHECK_IN")

        # Step 6: Check-Out (Cycle 2) -> Must succeed
        p4 = service.record_punch(
            tenant_id=tenant.id,
            student_id=student.id,
            node_id="MOBILE-APP",
            punch_type="CHECK_OUT",
            is_self_attendance=False,
        )
        self.assertTrue(p4.get("attendance_logged"))
        self.assertEqual(p4.get("punch_type"), "CHECK_OUT")

    def test_manual_override_strict_alternating_sequence(self):
        """Test manual override punch strictly enforces alternating sequence."""
        tenant = self.db.query(Tenant).filter(Tenant.tenant_type == "corporate", Tenant.is_deleted == False).first()
        test_roll = f"EMP-MANUAL-{int(datetime.now().timestamp()) % 100000}"
        student = Student(
            tenant_id=tenant.id,
            roll_number=test_roll,
            name="Manual Punch Employee",
            user_role="employee",
            is_active=True,
            employment_status="ACTIVE",
        )
        self.db.add(student)
        self.db.commit()
        self.db.refresh(student)

        service = AttendanceService(self.db)

        # 1. Manual checkout without checkin must raise 400
        class MockPayload:
            student_id = student.id
            node_id = None
            reason = "Test reason"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            punch_type = "CHECK_OUT"
            override_by = "Admin"

        with self.assertRaises(Exception) as cm:
            service.process_manual_override(tenant, MockPayload)
        self.assertIn("400", str(cm.exception))

        # 2. Manual AUTO punch -> creates Check-In
        MockPayload.punch_type = "AUTO"
        r1 = service.process_manual_override(tenant, MockPayload)
        self.assertEqual(r1.get("punch_type"), "CHECK_IN")

        # 3. Manual Check-In while already checked in -> must raise 400
        MockPayload.punch_type = "CHECK_IN"
        with self.assertRaises(Exception) as cm2:
            service.process_manual_override(tenant, MockPayload)
        self.assertIn("400", str(cm2.exception))

        # 4. Manual AUTO punch -> creates Check-Out
        MockPayload.punch_type = "AUTO"
        r2 = service.process_manual_override(tenant, MockPayload)
        self.assertEqual(r2.get("punch_type"), "CHECK_OUT")


if __name__ == "__main__":
    unittest.main()
