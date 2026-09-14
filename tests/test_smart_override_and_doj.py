"""
Integration tests for Employee Date of Joining (DOJ), Smart Manual Override Toggle,
and Employee Punch Status querying.
"""
import os
import sys
from datetime import datetime, date, timedelta
from pathlib import Path
import unittest
from fastapi.testclient import TestClient

# Setup path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.database.session import init_db, get_db_context
from src.database.models import Tenant, User, Student, AttendanceRecord, SystemBranding
from src.server.app import app
from src.utils.timezone import get_ist_now, get_ist_date


class TestSmartOverrideAndDOJ(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        with get_db_context() as db:
            self.tenant = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            if not self.tenant:
                self.tenant = db.query(Tenant).first()
            self.tenant_id = self.tenant.id

            # Clean test students
            test_rolls = ["EMP_DOJ_TEST_001", "EMP_DOJ_TEST_002"]
            st_ids = [s.id for s in db.query(Student).filter(Student.roll_number.in_(test_rolls)).all()]
            if st_ids:
                db.query(AttendanceRecord).filter(AttendanceRecord.student_id.in_(st_ids)).delete(synchronize_session=False)
                db.query(Student).filter(Student.id.in_(st_ids)).delete(synchronize_session=False)
                db.commit()

        self.client = TestClient(
            app,
            cookies={"active_tenant_id": str(self.tenant_id), "active_role": "ADMIN"},
            headers={"X-Tenant-ID": str(self.tenant_id)},
        )

    def tearDown(self):
        with get_db_context() as db:
            test_rolls = ["EMP_DOJ_TEST_001", "EMP_DOJ_TEST_002"]
            st_ids = [s.id for s in db.query(Student).filter(Student.roll_number.in_(test_rolls)).all()]
            if st_ids:
                db.query(AttendanceRecord).filter(AttendanceRecord.student_id.in_(st_ids)).delete(synchronize_session=False)
                db.query(Student).filter(Student.id.in_(st_ids)).delete(synchronize_session=False)
                db.commit()

    def test_student_enrollment_with_doj(self):
        """Verify student creation preserves date_of_joining and defaults to today if corporate."""
        custom_doj = "2024-03-15"
        payload = {
            "roll_number": "EMP_DOJ_TEST_001",
            "name": "Jane Developer",
            "department": "Engineering",
            "user_role": "employee",
            "date_of_joining": custom_doj,
        }
        res = self.client.post("/api/v1/enroll/student", json=payload)
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        student_id = data["student"]["id"]
        self.assertEqual(data["student"]["date_of_joining"], custom_doj)

        # Update profile with new DOJ
        updated_doj = "2023-08-01"
        up_payload = {
            "roll_number": "EMP_DOJ_TEST_001",
            "name": "Jane Senior Developer",
            "department": "Engineering",
            "user_role": "employee",
            "date_of_joining": updated_doj,
        }
        res_up = self.client.put(f"/api/v1/enroll/student/{student_id}", json=up_payload)
        self.assertEqual(res_up.status_code, 200, res_up.text)
        up_data = res_up.json()
        self.assertEqual(up_data["student"]["date_of_joining"], updated_doj)

    def test_smart_manual_override_checkin_and_checkout_cycle(self):
        """Verify smart manual override automatically performs Check-In then Check-Out."""
        with get_db_context() as db:
            student = Student(
                tenant_id=self.tenant_id,
                roll_number="EMP_DOJ_TEST_002",
                name="Smart Override Tester",
                department="Operations",
                user_role="employee",
                date_of_joining=get_ist_date(),
            )
            db.add(student)
            db.commit()
            db.refresh(student)
            student_id = student.id

        # 1. Query initial employee status -> NOT_CHECKED_IN
        res_st1 = self.client.get(f"/api/v1/attendance/employee-status/{student_id}")
        self.assertEqual(res_st1.status_code, 200)
        self.assertEqual(res_st1.json()["status"], "NOT_CHECKED_IN")
        self.assertEqual(res_st1.json()["next_action"], "CHECK_IN")

        # 2. Perform first manual override (AUTO) -> Should Check-In
        now_ist = get_ist_now()
        ts_in_str = now_ist.strftime("%Y-%m-%d %H:%M:%S")
        res_ov1 = self.client.post("/api/v1/attendance/manual-override", json={
            "student_id": student_id,
            "punch_type": "AUTO",
            "timestamp": ts_in_str,
            "reason": "Smart Check-In Test",
            "override_by": "Test Administrator",
        })
        self.assertEqual(res_ov1.status_code, 200, res_ov1.text)
        self.assertIn("Check-In", res_ov1.json()["message"])

        # 3. Query employee status -> CHECKED_IN
        res_st2 = self.client.get(f"/api/v1/attendance/employee-status/{student_id}")
        self.assertEqual(res_st2.status_code, 200)
        self.assertEqual(res_st2.json()["status"], "CHECKED_IN")
        self.assertEqual(res_st2.json()["next_action"], "CHECK_OUT")

        # 4. Perform second manual override (AUTO) after simulated shift time -> Should Check-Out
        ts_out_str = (now_ist + timedelta(hours=8, minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
        res_ov2 = self.client.post("/api/v1/attendance/manual-override", json={
            "student_id": student_id,
            "punch_type": "AUTO",
            "timestamp": ts_out_str,
            "reason": "Smart Check-Out Test",
            "override_by": "Test Administrator",
        })
        self.assertEqual(res_ov2.status_code, 200, res_ov2.text)
        self.assertIn("Check-Out", res_ov2.json()["message"])

        # 5. Query employee status -> CHECKED_OUT
        res_st3 = self.client.get(f"/api/v1/attendance/employee-status/{student_id}")
        self.assertEqual(res_st3.status_code, 200)
        self.assertEqual(res_st3.json()["status"], "CHECKED_OUT")


if __name__ == "__main__":
    unittest.main()
