"""
Unit & Integration Tests for Tenant-Scoped Logout Redirection, Corporate Check-In / Check-Out Engine,
and Shift Status & Export Processing.
"""
import os
import sys
from datetime import datetime, time, date, timedelta
from pathlib import Path
import unittest
from fastapi.testclient import TestClient

# Setup path
BASE_DIR = Path(__file__).resolve().parent.parent
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

from src.database.session import init_db, get_db_context
from src.database.models import Tenant, User, Student, AttendanceRecord, SystemBranding
from src.core.attendance_manager import AttendanceManager
from src.server.app import app


class TestCorporateCheckinCheckout(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.client = TestClient(app)
        self.attendance_mgr = AttendanceManager()
        # Clean any stale test students and records
        with get_db_context() as db:
            test_rolls = ["EMP_TEST_CORP_001", "EMP_TEST_CORP_002", "EMP_TEST_CORP_003", "EMP_TEST_CORP_004"]
            st_ids = [s.id for s in db.query(Student).filter(Student.roll_number.in_(test_rolls)).all()]
            if st_ids:
                db.query(AttendanceRecord).filter(AttendanceRecord.student_id.in_(st_ids)).delete(synchronize_session=False)
                db.query(Student).filter(Student.id.in_(st_ids)).delete(synchronize_session=False)
                db.commit()

    def tearDown(self):
        with get_db_context() as db:
            test_rolls = ["EMP_TEST_CORP_001", "EMP_TEST_CORP_002", "EMP_TEST_CORP_003", "EMP_TEST_CORP_004"]
            st_ids = [s.id for s in db.query(Student).filter(Student.roll_number.in_(test_rolls)).all()]
            if st_ids:
                db.query(AttendanceRecord).filter(AttendanceRecord.student_id.in_(st_ids)).delete(synchronize_session=False)
                db.query(Student).filter(Student.id.in_(st_ids)).delete(synchronize_session=False)
                db.commit()

    def test_tenant_scoped_logout_redirection(self):
        """Verify POST /api/v1/auth/logout returns appropriate tenant-scoped or super-admin URL."""
        # 1. Super Admin logout -> /super-admin/login
        client_sa = TestClient(app, cookies={"active_role": "SUPER_ADMIN"})
        res_sa = client_sa.post("/api/v1/auth/logout")
        self.assertEqual(res_sa.status_code, 200)
        self.assertEqual(res_sa.json().get("redirect_url"), "/super-admin/login")

        # 2. SSEC Corporate Admin / Employee logout -> /login/ssec
        with get_db_context() as db:
            ssec = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            self.assertIsNotNone(ssec)
            ssec_id = str(ssec.id)

        client_ssec = TestClient(app, cookies={
            "active_role": "EMPLOYEE",
            "active_tenant_id": ssec_id
        })
        res_ssec = client_ssec.post("/api/v1/auth/logout")
        self.assertEqual(res_ssec.status_code, 200)
        self.assertEqual(res_ssec.json().get("redirect_url"), "/login/ssec")

        # 3. Default Educational Portal logout -> /login/default
        with get_db_context() as db:
            default_t = db.query(Tenant).filter(Tenant.slug == "default").first()
            self.assertIsNotNone(default_t)
            default_id = str(default_t.id)

        client_def = TestClient(app, cookies={
            "active_role": "STUDENT",
            "active_tenant_id": default_id
        })
        res_def = client_def.post("/api/v1/auth/logout")
        self.assertEqual(res_def.status_code, 200)
        self.assertEqual(res_def.json().get("redirect_url"), "/login/default")

        # 4. Anonymous / Unspecified logout -> /login
        client_anon = TestClient(app)
        res_anon = client_anon.post("/api/v1/auth/logout")
        self.assertEqual(res_anon.status_code, 200)
        self.assertEqual(res_anon.json().get("redirect_url"), "/login")

    def test_corporate_checkin_and_checkout_lifecycle(self):
        """Verify full Check-In, Cooldown rejection, Check-Out, and duration calculation for corporate tenants."""
        with get_db_context() as db:
            ssec = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            self.assertIsNotNone(ssec)

            # Ensure shift branding is configured
            branding = db.query(SystemBranding).filter(SystemBranding.tenant_id == ssec.id).first()
            if not branding:
                branding = SystemBranding(
                    tenant_id=ssec.id,
                    institution_name="SSEC Corporate",
                    tenant_type="corporate",
                    shift_check_in_time="10:30",
                    shift_check_out_time="18:00",
                    shift_grace_minutes=15,
                    min_checkout_interval_minutes=15,
                )
                db.add(branding)
            else:
                branding.tenant_type = "corporate"
                branding.shift_check_in_time = "10:30"
                branding.shift_check_out_time = "18:00"
                branding.shift_grace_minutes = 15
                branding.min_checkout_interval_minutes = 15
            db.commit()

            # Create test corporate employee
            emp = Student(
                tenant_id=ssec.id,
                roll_number="EMP_TEST_CORP_001",
                name="Corporate Test User",
                department="Engineering",
                user_role="employee",
                is_active=True
            )
            db.add(emp)
            db.commit()
            db.refresh(emp)

            emp_id = emp.id
            ssec_id = ssec.id

        # Clear attendance manager cache for clean test state
        self.attendance_mgr._last_logged_cache.clear()

        # 1. On-Time Check-In Punch (Simulate 10:15 AM)
        checkin_dt = datetime.combine(date.today(), time(10, 15, 0))
        res_in = self.attendance_mgr.mark_attendance(
            student_id=emp_id,
            node_id="TEST_GATE_1",
            confidence_distance=0.25,
            now_dt=checkin_dt,
            tenant_id=ssec_id
        )
        self.assertTrue(res_in["attendance_logged"])
        self.assertEqual(res_in["punch_type"], "CHECK_IN")
        self.assertEqual(res_in["shift_status"], "ON_TIME")

        with get_db_context() as db:
            rec = db.query(AttendanceRecord).filter(AttendanceRecord.student_id == emp_id).first()
            self.assertIsNotNone(rec)
            self.assertEqual(rec.punch_type, "CHECK_IN")
            self.assertEqual(rec.shift_status, "ON_TIME")
            self.assertIsNotNone(rec.check_in_time)
            self.assertIsNone(rec.check_out_time)
            self.assertIsNone(rec.work_duration_minutes)

        # 2. Double Tap / Buffer Window Rejection (Simulate 10:20 AM - 5 mins after check-in, buffer is 15 mins)
        too_soon_dt = datetime.combine(date.today(), time(10, 20, 0))
        res_cooldown = self.attendance_mgr.mark_attendance(
            student_id=emp_id,
            node_id="TEST_GATE_1",
            confidence_distance=0.25,
            now_dt=too_soon_dt,
            tenant_id=ssec_id
        )
        self.assertFalse(res_cooldown["attendance_logged"])
        self.assertTrue(res_cooldown["cooldown_active"])
        self.assertIn("Check-In already logged", res_cooldown["message"])

        # 3. Completed Check-Out Punch (Simulate 18:15 PM - after shift end 18:00)
        checkout_dt = datetime.combine(date.today(), time(18, 15, 0))
        res_out = self.attendance_mgr.mark_attendance(
            student_id=emp_id,
            node_id="TEST_GATE_1",
            confidence_distance=0.25,
            now_dt=checkout_dt,
            tenant_id=ssec_id
        )
        self.assertTrue(res_out["attendance_logged"])
        self.assertEqual(res_out["punch_type"], "CHECK_OUT")
        self.assertEqual(res_out["shift_status"], "COMPLETED")
        self.assertEqual(res_out["work_duration_minutes"], 480)  # 18:15 - 10:15 = 8 hours = 480 mins

        with get_db_context() as db:
            rec = db.query(AttendanceRecord).filter(AttendanceRecord.student_id == emp_id).first()
            self.assertIsNotNone(rec)
            self.assertEqual(rec.punch_type, "CHECK_OUT")
            self.assertEqual(rec.shift_status, "COMPLETED")
            self.assertIsNotNone(rec.check_out_time)
            self.assertEqual(rec.work_duration_minutes, 480)

    def test_corporate_late_checkin_and_early_departure(self):
        """Verify Late Check-In and Early Departure shift statuses."""
        with get_db_context() as db:
            ssec = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            self.assertIsNotNone(ssec)

            emp = Student(
                tenant_id=ssec.id,
                roll_number="EMP_TEST_CORP_002",
                name="Late Test User",
                department="QA",
                user_role="employee",
                is_active=True
            )
            db.add(emp)
            db.commit()
            db.refresh(emp)

            emp_id = emp.id
            ssec_id = ssec.id

        self.attendance_mgr._last_logged_cache.clear()

        # 1. Late Check-In (11:00 AM, shift is 10:30 + 15m grace = 10:45 cutoff)
        late_checkin_dt = datetime.combine(date.today(), time(11, 0, 0))
        res_in = self.attendance_mgr.mark_attendance(
            student_id=emp_id,
            node_id="TEST_GATE_1",
            confidence_distance=0.25,
            now_dt=late_checkin_dt,
            tenant_id=ssec_id
        )
        self.assertTrue(res_in["attendance_logged"])
        self.assertEqual(res_in["shift_status"], "LATE_CHECKIN")

        # 2. Early Departure (16:30 PM, before shift end 18:00)
        early_checkout_dt = datetime.combine(date.today(), time(16, 30, 0))
        res_out = self.attendance_mgr.mark_attendance(
            student_id=emp_id,
            node_id="TEST_GATE_1",
            confidence_distance=0.25,
            now_dt=early_checkout_dt,
            tenant_id=ssec_id
        )
        self.assertTrue(res_out["attendance_logged"])
        self.assertEqual(res_out["shift_status"], "EARLY_DEPARTURE")
        self.assertEqual(res_out["work_duration_minutes"], 330)  # 16:30 - 11:00 = 5h30m = 330m

    def test_dynamic_missed_checkout_evaluation(self):
        """Verify dynamic serialization evaluates unclosed past shifts as MISSED_CHECKOUT."""
        with get_db_context() as db:
            ssec = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            emp = Student(
                tenant_id=ssec.id,
                roll_number="EMP_TEST_CORP_003",
                name="Missed Out Test User",
                department="Finance",
                user_role="employee",
                is_active=True
            )
            db.add(emp)
            db.commit()
            db.refresh(emp)

            # Record from yesterday with only check_in_time
            yesterday_dt = datetime.now() - timedelta(days=1)
            past_rec = AttendanceRecord(
                tenant_id=ssec.id,
                student_id=emp.id,
                node_id="GATE_1",
                timestamp=yesterday_dt,
                confidence_distance=0.25,
                punch_type="CHECK_IN",
                check_in_time=yesterday_dt,
                shift_status="ON_TIME"
            )
            db.add(past_rec)
            db.commit()

            emp_id = emp.id
            ssec_id = ssec.id

        client = TestClient(app, cookies={
            "active_tenant_id": str(ssec_id),
            "active_role": "TENANT_ADMIN"
        })

        # Query attendance records API
        res = client.get(f"/api/v1/attendance/records?tenant_id={ssec_id}&roll_number=EMP_TEST_CORP_003")
        self.assertEqual(res.status_code, 200)
        records = res.json().get("records", [])
        self.assertTrue(len(records) > 0)
        self.assertEqual(records[0]["shift_status"], "MISSED_CHECKOUT")

    def test_corporate_export_and_stats(self):
        """Verify corporate stats include checked in/out counts and export includes corporate columns."""
        with get_db_context() as db:
            ssec = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            ssec_id = ssec.id

            emp = Student(
                tenant_id=ssec.id,
                roll_number="EMP_TEST_CORP_004",
                name="Export Test User",
                department="HR",
                user_role="employee",
                is_active=True
            )
            db.add(emp)
            db.commit()
            db.refresh(emp)

            now_dt = datetime.now()
            rec = AttendanceRecord(
                tenant_id=ssec.id,
                student_id=emp.id,
                node_id="GATE_1",
                timestamp=now_dt,
                confidence_distance=0.25,
                punch_type="CHECK_IN",
                check_in_time=now_dt,
                shift_status="ON_TIME"
            )
            db.add(rec)
            db.commit()

            emp_id = emp.id

        client = TestClient(app, cookies={
            "active_tenant_id": str(ssec_id),
            "active_role": "TENANT_ADMIN"
        })

        # 1. Stats endpoint
        res_stats = client.get(f"/api/v1/attendance/stats?tenant_id={ssec_id}")
        self.assertEqual(res_stats.status_code, 200)
        data = res_stats.json()
        self.assertIn("checked_in_today", data)
        self.assertIn("checked_out_today", data)
        self.assertIn("shift_hours_display", data)

    def test_corporate_multi_punch_sessions(self):
        """Verify multi-punch session toggling (Check-In -> Check-Out -> Re-Entry Check-In -> Final Check-Out)."""
        with get_db_context() as db:
            ssec = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            self.assertIsNotNone(ssec)
            ssec_id = ssec.id

            emp = Student(
                tenant_id=ssec_id,
                roll_number="EMP_TEST_CORP_001",
                name="Multi-Punch User",
                department="Engineering",
                user_role="employee",
                is_active=True
            )
            db.add(emp)
            db.commit()
            db.refresh(emp)
            emp_id = emp.id

        self.attendance_mgr._last_logged_cache.clear()

        # 1. First Check-In (09:30 AM)
        t1 = datetime.combine(date.today(), time(9, 30, 0))
        r1 = self.attendance_mgr.mark_attendance(
            student_id=emp_id,
            node_id="GATE_IN_1",
            confidence_distance=0.20,
            now_dt=t1,
            tenant_id=ssec_id
        )
        self.assertTrue(r1["attendance_logged"])
        self.assertEqual(r1["punch_type"], "CHECK_IN")

        # 2. Too Soon Rejection (09:35 AM)
        t_soon = datetime.combine(date.today(), time(9, 35, 0))
        r_soon = self.attendance_mgr.mark_attendance(
            student_id=emp_id,
            node_id="GATE_IN_1",
            confidence_distance=0.20,
            now_dt=t_soon,
            tenant_id=ssec_id
        )
        self.assertFalse(r_soon["attendance_logged"])
        self.assertTrue(r_soon["cooldown_active"])

        # 3. First Check-Out / Lunch Break (12:30 PM - 180 mins)
        t2 = datetime.combine(date.today(), time(12, 30, 0))
        r2 = self.attendance_mgr.mark_attendance(
            student_id=emp_id,
            node_id="GATE_OUT_1",
            confidence_distance=0.22,
            now_dt=t2,
            tenant_id=ssec_id
        )
        self.assertTrue(r2["attendance_logged"])
        self.assertEqual(r2["punch_type"], "CHECK_OUT")
        self.assertEqual(r2["work_duration_minutes"], 180)

        # 4. Too Soon Rejection after Check-Out (12:35 PM)
        t_soon2 = datetime.combine(date.today(), time(12, 35, 0))
        r_soon2 = self.attendance_mgr.mark_attendance(
            student_id=emp_id,
            node_id="GATE_OUT_1",
            confidence_distance=0.22,
            now_dt=t_soon2,
            tenant_id=ssec_id
        )
        self.assertFalse(r_soon2["attendance_logged"])
        self.assertTrue(r_soon2["cooldown_active"])

        # 5. Re-Entry Check-In (13:30 PM)
        t3 = datetime.combine(date.today(), time(13, 30, 0))
        r3 = self.attendance_mgr.mark_attendance(
            student_id=emp_id,
            node_id="GATE_IN_1",
            confidence_distance=0.19,
            now_dt=t3,
            tenant_id=ssec_id
        )
        self.assertTrue(r3["attendance_logged"])
        self.assertEqual(r3["punch_type"], "CHECK_IN")

        # 6. Final Shift Check-Out (18:00 PM - 270 mins)
        t4 = datetime.combine(date.today(), time(18, 0, 0))
        r4 = self.attendance_mgr.mark_attendance(
            student_id=emp_id,
            node_id="GATE_OUT_1",
            confidence_distance=0.21,
            now_dt=t4,
            tenant_id=ssec_id
        )
        self.assertTrue(r4["attendance_logged"])
        self.assertEqual(r4["punch_type"], "CHECK_OUT")
        self.assertEqual(r4["work_duration_minutes"], 270)

        # Verify DB has exactly 2 closed session records for today
        with get_db_context() as db:
            records = (
                db.query(AttendanceRecord)
                .filter(
                    AttendanceRecord.tenant_id == ssec_id,
                    AttendanceRecord.student_id == emp_id
                )
                .order_by(AttendanceRecord.timestamp.asc())
                .all()
            )
            self.assertEqual(len(records), 2)
            self.assertEqual(records[0].work_duration_minutes, 180)
            self.assertEqual(records[1].work_duration_minutes, 270)
            total_active_mins = sum(r.work_duration_minutes for r in records if r.work_duration_minutes)
            self.assertEqual(total_active_mins, 450)


if __name__ == "__main__":
    unittest.main()
