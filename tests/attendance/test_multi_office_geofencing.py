import unittest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.server.app import app
from src.database.session import SessionLocal
from src.database.models import (
    Tenant,
    User,
    Student,
    CompanyLocation,
    SystemBranding,
    AttendanceRecord,
)
from src.utils.auth_utils import hash_password
from src.server.routes.api_employee_portal import create_employee_token
from src.server.rbac_middleware import create_access_token


class TestMultiOfficeGeofencing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db: Session = SessionLocal()

        # 1. Setup Test Corporate Tenant
        cls.tenant = cls.db.query(Tenant).filter(Tenant.slug == "test-multioffice").first()
        if not cls.tenant:
            cls.tenant = Tenant(
                name="Multi-Office Test Corp",
                slug="test-multioffice",
                tenant_type="corporate",
                subscription_plan="PRO",
                subscription_status="ACTIVE",
                is_active=True,
            )
            cls.db.add(cls.tenant)
            cls.db.flush()

        cls.tenant_id = cls.tenant.id

        # 2. Setup Tenant Admin User
        cls.admin_user = cls.db.query(User).filter(User.username == "admin_multioffice").first()
        if not cls.admin_user:
            cls.admin_user = User(
                tenant_id=cls.tenant_id,
                username="admin_multioffice",
                email="admin_multioffice@test.com",
                password_hash=hash_password("admin123"),
                role="TENANT_ADMIN",
                full_name="Admin Multi-Office",
                is_active=True,
            )
            cls.db.add(cls.admin_user)
            cls.db.flush()

        # 3. Setup Branding (Global campus coordinates)
        cls.branding = cls.db.query(SystemBranding).filter(SystemBranding.tenant_id == cls.tenant_id).first()
        if not cls.branding:
            cls.branding = SystemBranding(
                tenant_id=cls.tenant_id,
                institution_name="Multi-Office Hub",
                enable_self_attendance=True,
                geo_latitude=18.5204,
                geo_longitude=73.8567,
                geo_radius_meters=150.0,
                mobile_require_face_verification=False,
            )
            cls.db.add(cls.branding)
        else:
            cls.branding.enable_self_attendance = True
            cls.branding.geo_latitude = 18.5204
            cls.branding.geo_longitude = 73.8567
            cls.branding.geo_radius_meters = 150.0
            cls.branding.mobile_require_face_verification = False
        cls.db.flush()

        # 4. Create Office Locations
        # Office 1: Geofencing DISABLED
        cls.loc_disabled = cls.db.query(CompanyLocation).filter(
            CompanyLocation.tenant_id == cls.tenant_id,
            CompanyLocation.name == "Branch Bypass HQ",
        ).first()
        if not cls.loc_disabled:
            cls.loc_disabled = CompanyLocation(
                tenant_id=cls.tenant_id,
                name="Branch Bypass HQ",
                code="BYP-01",
                city="Pune",
                state="Maharashtra",
                latitude=18.5204,
                longitude=73.8567,
                radius_meters=100.0,
                self_attendance_geofencing_enabled=False,
                is_active=True,
            )
            cls.db.add(cls.loc_disabled)
            cls.db.flush()
        else:
            cls.loc_disabled.self_attendance_geofencing_enabled = False
            cls.db.flush()

        # Office 2: Geofencing ENABLED (Mumbai coordinates: 19.0760, 72.8777)
        cls.loc_mumbai = cls.db.query(CompanyLocation).filter(
            CompanyLocation.tenant_id == cls.tenant_id,
            CompanyLocation.name == "Mumbai Branch Office",
        ).first()
        if not cls.loc_mumbai:
            cls.loc_mumbai = CompanyLocation(
                tenant_id=cls.tenant_id,
                name="Mumbai Branch Office",
                code="MUM-01",
                city="Mumbai",
                state="Maharashtra",
                latitude=19.0760,
                longitude=72.8777,
                radius_meters=200.0,
                self_attendance_geofencing_enabled=True,
                is_active=True,
            )
            cls.db.add(cls.loc_mumbai)
            cls.db.flush()
        else:
            cls.loc_mumbai.latitude = 19.0760
            cls.loc_mumbai.longitude = 72.8777
            cls.loc_mumbai.radius_meters = 200.0
            cls.loc_mumbai.self_attendance_geofencing_enabled = True
            cls.db.flush()

        # Office 3: Geofencing ENABLED (Bangalore coordinates: 12.9716, 77.5946)
        cls.loc_blr = cls.db.query(CompanyLocation).filter(
            CompanyLocation.tenant_id == cls.tenant_id,
            CompanyLocation.name == "Bangalore Tech Hub",
        ).first()
        if not cls.loc_blr:
            cls.loc_blr = CompanyLocation(
                tenant_id=cls.tenant_id,
                name="Bangalore Tech Hub",
                code="BLR-01",
                city="Bengaluru",
                state="Karnataka",
                latitude=12.9716,
                longitude=77.5946,
                radius_meters=150.0,
                self_attendance_geofencing_enabled=True,
                is_active=True,
            )
            cls.db.add(cls.loc_blr)
            cls.db.flush()
        else:
            cls.loc_blr.latitude = 12.9716
            cls.loc_blr.longitude = 77.5946
            cls.loc_blr.radius_meters = 150.0
            cls.loc_blr.self_attendance_geofencing_enabled = True
            cls.db.flush()

        # 5. Create Test Employees
        # Emp 1: Unassigned Office (location_id = None)
        cls.emp_unassigned = cls.db.query(Student).filter(
            Student.tenant_id == cls.tenant_id,
            Student.roll_number == "EMP-UNASSIGNED",
        ).first()
        if not cls.emp_unassigned:
            cls.emp_unassigned = Student(
                tenant_id=cls.tenant_id,
                name="Unassigned Office Employee",
                roll_number="EMP-UNASSIGNED",
                user_role="employee",
                location_id=None,
                is_active=True,
            )
            cls.db.add(cls.emp_unassigned)
            cls.db.flush()

        # Emp 2: Assigned to Bypass Office (geofencing disabled)
        cls.emp_bypassed = cls.db.query(Student).filter(
            Student.tenant_id == cls.tenant_id,
            Student.roll_number == "EMP-BYPASS",
        ).first()
        if not cls.emp_bypassed:
            cls.emp_bypassed = Student(
                tenant_id=cls.tenant_id,
                name="Bypassed Office Employee",
                roll_number="EMP-BYPASS",
                user_role="employee",
                location_id=cls.loc_disabled.id,
                is_active=True,
            )
            cls.db.add(cls.emp_bypassed)
            cls.db.flush()

        # Emp 3: Assigned to Mumbai Office (geofencing enabled)
        cls.emp_mumbai = cls.db.query(Student).filter(
            Student.tenant_id == cls.tenant_id,
            Student.roll_number == "EMP-MUMBAI",
        ).first()
        if not cls.emp_mumbai:
            cls.emp_mumbai = Student(
                tenant_id=cls.tenant_id,
                name="Mumbai Office Employee",
                roll_number="EMP-MUMBAI",
                user_role="employee",
                location_id=cls.loc_mumbai.id,
                is_active=True,
            )
            cls.db.add(cls.emp_mumbai)
            cls.db.flush()

        # Emp 4: Assigned to Bangalore Office (geofencing enabled)
        cls.emp_blr = cls.db.query(Student).filter(
            Student.tenant_id == cls.tenant_id,
            Student.roll_number == "EMP-BLR",
        ).first()
        if not cls.emp_blr:
            cls.emp_blr = Student(
                tenant_id=cls.tenant_id,
                name="Bangalore Office Employee",
                roll_number="EMP-BLR",
                user_role="employee",
                location_id=cls.loc_blr.id,
                is_active=True,
            )
            cls.db.add(cls.emp_blr)
            cls.db.flush()

        cls.db.commit()

        # Generate tokens
        cls.token_unassigned = create_employee_token(
            student_id=cls.emp_unassigned.id,
            tenant_id=cls.tenant_id,
            roll_number=cls.emp_unassigned.roll_number,
            name=cls.emp_unassigned.name,
        )
        cls.token_bypassed = create_employee_token(
            student_id=cls.emp_bypassed.id,
            tenant_id=cls.tenant_id,
            roll_number=cls.emp_bypassed.roll_number,
            name=cls.emp_bypassed.name,
        )
        cls.token_mumbai = create_employee_token(
            student_id=cls.emp_mumbai.id,
            tenant_id=cls.tenant_id,
            roll_number=cls.emp_mumbai.roll_number,
            name=cls.emp_mumbai.name,
        )
        cls.token_blr = create_employee_token(
            student_id=cls.emp_blr.id,
            tenant_id=cls.tenant_id,
            roll_number=cls.emp_blr.roll_number,
            name=cls.emp_blr.name,
        )
        cls.token_admin = create_access_token(
            user_id=cls.admin_user.id,
            role=cls.admin_user.role,
            tenant_id=cls.tenant_id,
            username=cls.admin_user.username,
        )

    @classmethod
    def tearDownClass(cls):
        # Clean up created attendance records
        cls.db.query(AttendanceRecord).filter(AttendanceRecord.tenant_id == cls.tenant_id).delete()
        cls.db.commit()
        cls.db.close()

    def test_01_unassigned_employee_geofence_disabled_by_default(self):
        """Unassigned employees should have geofencing disabled by default and check in from any location."""
        # 1. Check geofence config endpoint
        res = self.client.get(
            "/api/v1/employee/geofence/config",
            headers={"Authorization": f"Bearer {self.token_unassigned}"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data["geofence_enabled"])
        self.assertFalse(data["is_location_assigned"])

        # 2. Check-in from an arbitrary coordinate (e.g. Delhi: 28.6139, 77.2090)
        checkin_payload = {
            "latitude": 28.6139,
            "longitude": 77.2090,
            "accuracy": 15.0,
            "punch_type": "CHECK_IN",
        }
        res_checkin = self.client.post(
            "/api/v1/employee/check-in",
            json=checkin_payload,
            headers={"Authorization": f"Bearer {self.token_unassigned}"},
        )
        self.assertEqual(res_checkin.status_code, 200, res_checkin.text)
        self.assertTrue(res_checkin.json().get("attendance_logged"))

    def test_02_assigned_office_geofence_disabled_allows_arbitrary_location(self):
        """Employee in office with geofence disabled should be allowed to check in from any coordinates."""
        # 1. Config endpoint
        res = self.client.get(
            "/api/v1/employee/geofence/config",
            headers={"Authorization": f"Bearer {self.token_bypassed}"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data["geofence_enabled"])
        self.assertEqual(data["location_name"], "Branch Bypass HQ")

        # 2. Check-in from arbitrary coordinate (e.g. Goa: 15.2993, 74.1240)
        checkin_payload = {
            "latitude": 15.2993,
            "longitude": 74.1240,
            "accuracy": 10.0,
            "punch_type": "CHECK_IN",
        }
        res_checkin = self.client.post(
            "/api/v1/employee/check-in",
            json=checkin_payload,
            headers={"Authorization": f"Bearer {self.token_bypassed}"},
        )
        self.assertEqual(res_checkin.status_code, 200, res_checkin.text)
        self.assertTrue(res_checkin.json().get("attendance_logged"))

    def test_03_mumbai_office_geofence_enforced(self):
        """Mumbai office employee must be inside Mumbai radius; outside should return 403."""
        # 1. Inside Mumbai radius (~10m away from 19.0760, 72.8777)
        res_inside = self.client.post(
            "/api/v1/employee/check-in",
            json={"latitude": 19.07605, "longitude": 72.87775, "accuracy": 10.0, "punch_type": "CHECK_IN"},
            headers={"Authorization": f"Bearer {self.token_mumbai}"},
        )
        self.assertEqual(res_inside.status_code, 200, res_inside.text)

        # 2. Outside Mumbai radius (e.g. Pune coordinates: 18.5204, 73.8567 -> ~120km away)
        res_outside = self.client.post(
            "/api/v1/employee/check-in",
            json={"latitude": 18.5204, "longitude": 73.8567, "accuracy": 10.0, "punch_type": "CHECK_OUT"},
            headers={"Authorization": f"Bearer {self.token_mumbai}"},
        )
        self.assertEqual(res_outside.status_code, 403)
        self.assertIn("Outside geofenced perimeter for assigned office 'Mumbai Branch Office'", res_outside.json()["detail"])

    def test_04_bangalore_office_independent_boundary(self):
        """Bangalore office employee is evaluated strictly against Bangalore coordinates."""
        # Config check
        res = self.client.get(
            "/api/v1/employee/geofence/config",
            headers={"Authorization": f"Bearer {self.token_blr}"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["geofence_enabled"])
        self.assertEqual(data["location_name"], "Bangalore Tech Hub")
        self.assertAlmostEqual(data["center_latitude"], 12.9716, places=3)
        self.assertAlmostEqual(data["center_longitude"], 77.5946, places=3)

        # Inside Bangalore (~15m away)
        res_inside = self.client.post(
            "/api/v1/employee/check-in",
            json={"latitude": 12.97165, "longitude": 77.59465, "accuracy": 10.0, "punch_type": "CHECK_IN"},
            headers={"Authorization": f"Bearer {self.token_blr}"},
        )
        self.assertEqual(res_inside.status_code, 200, res_inside.text)

    def test_05_admin_location_masters_crud_with_geofence(self):
        """Admin can create and update office locations with geofence parameters."""
        headers = {
            "Authorization": f"Bearer {self.token_admin}",
            "X-Tenant-Slug": self.tenant.slug,
        }

        # 1. Create location
        create_payload = {
            "name": "Hyderabad Development Center",
            "code": "HYD-01",
            "city": "Hyderabad",
            "state": "Telangana",
            "latitude": 17.3850,
            "longitude": 78.4867,
            "radius_meters": 250.0,
            "self_attendance_geofencing_enabled": True,
            "is_active": True,
        }
        res_create = self.client.post(
            "/api/v1/payroll/masters/locations",
            json=create_payload,
            headers=headers,
        )
        self.assertEqual(res_create.status_code, 200, res_create.text)
        loc_id = res_create.json()["data"]["id"]
        self.assertTrue(res_create.json()["data"]["self_attendance_geofencing_enabled"])
        self.assertEqual(res_create.json()["data"]["radius_meters"], 250.0)

        # 2. Update location to disable geofencing
        update_payload = {
            "self_attendance_geofencing_enabled": False,
            "radius_meters": 300.0,
        }
        res_update = self.client.put(
            f"/api/v1/payroll/masters/locations/{loc_id}",
            json=update_payload,
            headers=headers,
        )
        self.assertEqual(res_update.status_code, 200, res_update.text)
        self.assertFalse(res_update.json()["data"]["self_attendance_geofencing_enabled"])
        self.assertEqual(res_update.json()["data"]["radius_meters"], 300.0)

        # 3. Clean up created location
        self.client.delete(f"/api/v1/payroll/masters/locations/{loc_id}", headers=headers)


if __name__ == "__main__":
    unittest.main()
