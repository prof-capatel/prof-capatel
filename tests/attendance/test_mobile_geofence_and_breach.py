"""
Unit & Integration Tests for:
- Mobile & Web Geofence Self Check-In / Check-Out
- Anti-Mock GPS Coordinate Verification
- Background Geofence Heartbeat & Out-of-Bounds Breach Lifecycle
- Admin Geofence Breach Audit Trail Endpoint
"""
import os
import sys
from datetime import datetime, date, timedelta
from pathlib import Path
import unittest
from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.database.session import init_db, get_db_context
from src.database.models import (
    Tenant,
    Student,
    AttendanceRecord,
    SystemBranding,
    EmployeeGeofenceBreach,
    WorkShift,
)
from src.server.app import app
from src.server.routes.api_employee_portal import create_employee_token, EMP_COOKIE_NAME
from src.utils.timezone import get_ist_now


class TestMobileGeofenceAndBreach(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.client = TestClient(app)
        self.test_roll = "EMP_MOCK_MOBILE_999"
        self.test_tenant_slug = "ssec"

        with get_db_context() as db:
            tenant = db.query(Tenant).filter(Tenant.slug == self.test_tenant_slug).first()
            self.assertIsNotNone(tenant, f"Tenant {self.test_tenant_slug} must exist")
            self.tenant_id = tenant.id

            # Ensure SystemBranding geofence is explicitly configured for testing:
            # Center: 21.7645, 72.1519 (Bhavnagar, SSEC)
            # Radius: 150 meters
            branding = db.query(SystemBranding).filter(SystemBranding.tenant_id == self.tenant_id).first()
            if not branding:
                branding = SystemBranding(tenant_id=self.tenant_id)
                db.add(branding)
            branding.geo_latitude = 21.764500
            branding.geo_longitude = 72.151900
            branding.geofence_radius = 150
            branding.enable_self_attendance = True
            branding.mobile_require_face_verification = False
            db.commit()

            # Clean any leftover test student, punches, and breaches
            stale = db.query(Student).filter(
                Student.tenant_id == self.tenant_id,
                Student.roll_number == self.test_roll
            ).first()
            if stale:
                db.query(EmployeeGeofenceBreach).filter(EmployeeGeofenceBreach.student_id == stale.id).delete()
                db.query(AttendanceRecord).filter(AttendanceRecord.student_id == stale.id).delete()
                db.delete(stale)
                db.commit()

            # Create fresh active employee
            emp = Student(
                tenant_id=self.tenant_id,
                name="Mobile Test Employee",
                roll_number=self.test_roll,
                department="Mobile Dev",
                designation="Software Engineer",
                is_active=True,
                employment_status="ACTIVE",
            )
            db.add(emp)
            db.commit()
            db.refresh(emp)
            self.student_id = emp.id

            # Generate valid employee authentication token
            self.token = create_employee_token(
                student_id=self.student_id,
                tenant_id=self.tenant_id,
                roll_number=self.test_roll,
                name="Mobile Test Employee",
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

    def test_01_geofence_config_endpoint(self):
        """Verify GET /api/v1/employee/geofence/config returns tenant perimeter and verification policies."""
        res = self.client.get("/api/v1/employee/geofence/config", headers=self.auth_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("geofence_enabled"))
        self.assertAlmostEqual(data.get("center_latitude"), 21.764500, places=4)
        self.assertAlmostEqual(data.get("center_longitude"), 72.151900, places=4)
        self.assertEqual(data.get("radius_meters"), 150)
        self.assertFalse(data.get("mobile_require_face_verification"))

    def test_02_mock_gps_rejection(self):
        """Verify mock / spoofed GPS locations are strictly blocked."""
        payload = {
            "latitude": 21.764500,
            "longitude": 72.151900,
            "accuracy": 5.0,
            "is_mock_location": True,  # Spoof detected
            "device_info": "Rooted Android (Mock Provider)"
        }
        res = self.client.post("/api/v1/employee/check-in", json=payload, headers=self.auth_headers)
        self.assertEqual(res.status_code, 403)
        self.assertIn("Mock GPS", res.json().get("detail", ""))

    def test_03_out_of_bounds_punch_rejection(self):
        """Verify punch is rejected when employee coordinates are outside the geofenced perimeter."""
        # Coordinates ~1.5km away from center (21.7800, 72.1600)
        payload = {
            "latitude": 21.780000,
            "longitude": 72.160000,
            "accuracy": 10.0,
            "is_mock_location": False,
            "device_info": "Mobile Chrome"
        }
        res = self.client.post("/api/v1/employee/check-in", json=payload, headers=self.auth_headers)
        self.assertEqual(res.status_code, 403)
        self.assertIn("Outside geofenced perimeter", res.json().get("detail", ""))

    def test_04_in_bounds_successful_checkin(self):
        """Verify employee inside perimeter records a valid CHECK_IN punch."""
        # Exactly at office center (21.764500, 72.151900)
        payload = {
            "latitude": 21.764500,
            "longitude": 72.151900,
            "accuracy": 8.0,
            "is_mock_location": False,
            "device_info": "Mobile Flutter App"
        }
        res = self.client.post("/api/v1/employee/check-in", json=payload, headers=self.auth_headers)
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("punch_type"), "CHECK_IN")
        self.assertEqual(data.get("punch_source"), "MOBILE_APP")

        # Verify punch in database
        with get_db_context() as db:
            punch = db.query(AttendanceRecord).filter(
                AttendanceRecord.student_id == self.student_id
            ).first()
            self.assertIsNotNone(punch)
            self.assertEqual(punch.punch_type, "CHECK_IN")
            self.assertEqual(punch.node_id, "MOBILE-APP")

    def test_05_punch_cooldown_enforcement(self):
        """Verify immediate second punch triggers anti-passback cooldown rejection."""
        payload = {
            "latitude": 21.764500,
            "longitude": 72.151900,
            "accuracy": 5.0,
            "is_mock_location": False,
            "device_info": "Mobile Flutter App"
        }
        # First punch
        res1 = self.client.post("/api/v1/employee/check-in", json=payload, headers=self.auth_headers)
        self.assertEqual(res1.status_code, 200)

        # Immediate repeat punch
        res2 = self.client.post("/api/v1/employee/check-in", json=payload, headers=self.auth_headers)
        self.assertEqual(res2.status_code, 400)
        detail = res2.json().get("detail", "").lower()
        self.assertTrue(
            "cooldown" in detail or "already recorded" in detail or "wait a moment" in detail,
            f"Unexpected detail: {detail}"
        )

    def test_06_geofence_heartbeat_lifecycle_and_audit(self):
        """
        Verify the complete out-of-bounds lifecycle:
        1. Employee checks in.
        2. Heartbeat sent outside perimeter creates an ACTIVE breach.
        3. Subsequent heartbeat updates breach duration.
        4. Heartbeat sent inside perimeter resolves the breach.
        5. Admin audit endpoint retrieves the breach records.
        """
        # Step 1: Punch In inside perimeter
        punch_res = self.client.post(
            "/api/v1/employee/check-in",
            json={"latitude": 21.764500, "longitude": 72.151900, "accuracy": 5.0, "is_mock_location": False},
            headers=self.auth_headers
        )
        self.assertEqual(punch_res.status_code, 200)

        # Step 2: Out-of-bounds heartbeat (approx 800m away: 21.7700, 72.1550)
        hb_outside_1 = self.client.post(
            "/api/v1/employee/geofence/heartbeat",
            json={"latitude": 21.770000, "longitude": 72.155000, "accuracy": 10.0, "is_mock_location": False},
            headers=self.auth_headers
        )
        self.assertEqual(hb_outside_1.status_code, 200)
        data1 = hb_outside_1.json()
        self.assertFalse(data1.get("is_within_geofence"))
        self.assertTrue(data1.get("breach_logged"))

        # Verify ACTIVE breach in database
        with get_db_context() as db:
            breach = db.query(EmployeeGeofenceBreach).filter(
                EmployeeGeofenceBreach.student_id == self.student_id,
                EmployeeGeofenceBreach.status == "ACTIVE"
            ).first()
            self.assertIsNotNone(breach)
            self.assertGreater(breach.distance_meters, 150)
            self.assertEqual(breach.status, "ACTIVE")

        # Step 3: Second out-of-bounds heartbeat
        hb_outside_2 = self.client.post(
            "/api/v1/employee/geofence/heartbeat",
            json={"latitude": 21.771000, "longitude": 72.156000, "accuracy": 12.0, "is_mock_location": False},
            headers=self.auth_headers
        )
        self.assertEqual(hb_outside_2.status_code, 200)

        # Step 4: In-bounds heartbeat (employee returns inside geofence perimeter)
        hb_inside = self.client.post(
            "/api/v1/employee/geofence/heartbeat",
            json={"latitude": 21.764500, "longitude": 72.151900, "accuracy": 6.0, "is_mock_location": False},
            headers=self.auth_headers
        )
        self.assertEqual(hb_inside.status_code, 200)
        data3 = hb_inside.json()
        self.assertTrue(data3.get("is_within_geofence"))
        self.assertTrue(data3.get("breach_resolved"))

        # Verify breach is now RESOLVED in database
        with get_db_context() as db:
            resolved_breach = db.query(EmployeeGeofenceBreach).filter(
                EmployeeGeofenceBreach.student_id == self.student_id
            ).order_by(EmployeeGeofenceBreach.id.desc()).first()
            self.assertIsNotNone(resolved_breach)
            self.assertEqual(resolved_breach.status, "RESOLVED")
            self.assertIsNotNone(resolved_breach.end_time)

        # Step 5: Admin retrieves geofence audit trail
        admin_res = self.client.get(
            f"/api/v1/attendance/geofence-breaches?student_id={self.student_id}",
            headers={"X-Tenant-ID": self.test_tenant_slug}
        )
        self.assertEqual(admin_res.status_code, 200)
        admin_data = admin_res.json()
        self.assertTrue(admin_data.get("success"))
        breaches = admin_data.get("breaches", [])
        self.assertGreaterEqual(len(breaches), 1)
        self.assertEqual(breaches[0]["roll_number"], self.test_roll)
        self.assertEqual(breaches[0]["status"], "RESOLVED")


if __name__ == "__main__":
    unittest.main()
