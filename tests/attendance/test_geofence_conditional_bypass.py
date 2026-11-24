"""
Unit tests for Conditional Geofencing Bypass:
- When Self-Attendance & Campus Geofencing is disabled (enable_self_attendance == False):
  * Employees can check in / check out from ANY location via the mobile application (node_id="MOBILE-APP").
  * Web portal self-attendance is rejected with HTTP 403.
  * Heartbeat returns bypassed status without creating breach records.
- When enabled (enable_self_attendance == True):
  * Strict radius validation is enforced for mobile check-in.
"""
import unittest
from pathlib import Path
import sys
from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.database.session import init_db, get_db_context
from src.database.models import Tenant, Student, SystemBranding, AttendanceRecord, EmployeeGeofenceBreach, CompanyLocation
from src.server.app import app
from src.server.routes.api_employee_portal import create_employee_token


class TestGeofenceConditionalBypass(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.client = TestClient(app)
        self.test_roll = "EMP_BYPASS_TEST_001"
        self.test_tenant_slug = "ssec"

        with get_db_context() as db:
            tenant = db.query(Tenant).filter(Tenant.slug == self.test_tenant_slug).first()
            self.assertIsNotNone(tenant)
            self.tenant_id = tenant.id

            branding = db.query(SystemBranding).filter(SystemBranding.tenant_id == self.tenant_id).first()
            if not branding:
                branding = SystemBranding(tenant_id=self.tenant_id)
                db.add(branding)
            # Set center: Bhavnagar, SSEC
            branding.geo_latitude = 21.764500
            branding.geo_longitude = 72.151900
            branding.geo_radius_meters = 150.0
            branding.enable_self_attendance = False  # Start with Geofencing DISABLED
            branding.mobile_require_face_verification = False
            db.commit()

            stale = db.query(Student).filter(
                Student.tenant_id == self.tenant_id,
                Student.roll_number == self.test_roll
            ).first()
            if stale:
                db.query(EmployeeGeofenceBreach).filter(EmployeeGeofenceBreach.student_id == stale.id).delete()
                db.query(AttendanceRecord).filter(AttendanceRecord.student_id == stale.id).delete()
                db.delete(stale)
                db.commit()

            loc = db.query(CompanyLocation).filter(
                CompanyLocation.tenant_id == self.tenant_id,
                CompanyLocation.name == "SSEC Main Campus",
            ).first()
            if not loc:
                loc = CompanyLocation(
                    tenant_id=self.tenant_id,
                    name="SSEC Main Campus",
                    code="SSEC-HQ",
                    latitude=21.764500,
                    longitude=72.151900,
                    radius_meters=150.0,
                    self_attendance_geofencing_enabled=False,
                    is_active=True,
                )
                db.add(loc)
                db.flush()
            else:
                loc.self_attendance_geofencing_enabled = False
                loc.latitude = 21.764500
                loc.longitude = 72.151900
                loc.radius_meters = 150.0
                db.flush()

            emp = Student(
                tenant_id=self.tenant_id,
                name="Bypass Test Employee",
                roll_number=self.test_roll,
                department="Mobile Dev",
                designation="Field Engineer",
                location_id=loc.id,
                is_active=True,
                employment_status="ACTIVE",
            )
            db.add(emp)
            db.commit()
            db.refresh(emp)
            self.student_id = emp.id

            self.token = create_employee_token(
                student_id=self.student_id,
                tenant_id=self.tenant_id,
                roll_number=self.test_roll,
                name="Bypass Test Employee",
            )
            self.auth_headers = {"Authorization": f"Bearer {self.token}"}

    def tearDown(self):
        with get_db_context() as db:
            stale = db.query(Student).filter(
                Student.tenant_id == self.tenant_id,
                Student.roll_number == self.test_roll
            ).first()
            if stale:
                db.query(EmployeeGeofenceBreach).filter(EmployeeGeofenceBreach.student_id == stale.id).delete()
                db.query(AttendanceRecord).filter(AttendanceRecord.student_id == stale.id).delete()
                db.delete(stale)
                db.commit()

    def test_mobile_checkin_allowed_from_anywhere_when_geofence_disabled(self):
        # Far away location: Ahmedabad (~180 km from Bhavnagar)
        payload = {
            "latitude": 23.0225,
            "longitude": 72.5714,
            "accuracy": 15.0,
            "is_mock_location": False,
        }
        res = self.client.post("/api/v1/employee/check-in", json=payload, headers=self.auth_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("attendance_logged", False))
        self.assertEqual(data.get("status"), "success")

    def test_web_portal_self_attendance_blocked_when_geofence_disabled(self):
        # Direct call to AttendanceService with node_id="SELF-ATTENDANCE" (web portal)
        from src.services.attendance_service import AttendanceService
        from fastapi import HTTPException

        with get_db_context() as db:
            service = AttendanceService(db)
            with self.assertRaises(HTTPException) as ctx:
                service.record_punch(
                    tenant_id=self.tenant_id,
                    student_id=self.student_id,
                    node_id="SELF-ATTENDANCE",
                    is_self_attendance=True,
                )
            self.assertEqual(ctx.exception.status_code, 403)
            self.assertIn("Self-attendance via web portal is disabled", ctx.exception.detail)

    def test_heartbeat_bypassed_when_geofence_disabled(self):
        # 1. First punch in
        payload = {
            "latitude": 23.0225,
            "longitude": 72.5714,
            "accuracy": 15.0,
            "is_mock_location": False,
        }
        self.client.post("/api/v1/employee/check-in", json=payload, headers=self.auth_headers)

        # 2. Dispatch heartbeat from far away
        hb_payload = {
            "latitude": 23.0225,
            "longitude": 72.5714,
            "accuracy": 15.0,
            "is_mock_location": False,
        }
        hb_res = self.client.post("/api/v1/employee/geofence/heartbeat", json=hb_payload, headers=self.auth_headers)
        self.assertEqual(hb_res.status_code, 200)
        hb_data = hb_res.json()
        self.assertEqual(hb_data.get("status"), "bypassed")
        self.assertTrue(hb_data.get("in_bounds"))

        # Verify no breach was created
        with get_db_context() as db:
            breaches = db.query(EmployeeGeofenceBreach).filter(
                EmployeeGeofenceBreach.student_id == self.student_id
            ).all()
            self.assertEqual(len(breaches), 0)

    def test_mobile_checkin_enforces_geofence_when_enabled(self):
        # Enable Geofencing
        with get_db_context() as db:
            loc = db.query(CompanyLocation).filter(
                CompanyLocation.tenant_id == self.tenant_id,
                CompanyLocation.name == "SSEC Main Campus",
            ).first()
            if loc:
                loc.self_attendance_geofencing_enabled = True
            branding = db.query(SystemBranding).filter(SystemBranding.tenant_id == self.tenant_id).first()
            branding.enable_self_attendance = True
            db.commit()

        # Punch from far away should be blocked
        payload = {
            "latitude": 23.0225,
            "longitude": 72.5714,
            "accuracy": 15.0,
            "is_mock_location": False,
        }
        res = self.client.post("/api/v1/employee/check-in", json=payload, headers=self.auth_headers)
        self.assertEqual(res.status_code, 403)
        self.assertIn("Outside geofenced perimeter", res.json().get("detail", ""))

        # Punch from within perimeter (~10 meters from center) should succeed
        near_payload = {
            "latitude": 21.764510,
            "longitude": 72.151910,
            "accuracy": 5.0,
            "is_mock_location": False,
        }
        res_near = self.client.post("/api/v1/employee/check-in", json=near_payload, headers=self.auth_headers)
        self.assertEqual(res_near.status_code, 200)
        self.assertTrue(res_near.json().get("attendance_logged", False))
