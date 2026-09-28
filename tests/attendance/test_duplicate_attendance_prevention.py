"""
Unit & Integration Tests for Duplicate Attendance Prevention on Live Dashboard Capture & Node Ingestion.
Tests concurrency locks, sliding in-memory debounce, frame-level deduplication,
and corporate multi-punch interval guards.
"""
import os
import sys
import time
import threading
from datetime import datetime, time as dtime, date, timedelta
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock
import numpy as np
from fastapi.testclient import TestClient

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

from src.database.session import init_db, get_db_context
from src.database.models import Tenant, User, Student, AttendanceRecord, SystemBranding, WorkShift
from src.core.attendance_manager import AttendanceManager
from src.server.app import app


class TestDuplicateAttendancePrevention(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.client = TestClient(app)
        self.attendance_mgr = AttendanceManager()
        # Reset cache
        self.attendance_mgr._last_logged_cache.clear()

        # Clean any stale test records
        self._cleanup_test_data()

        # Setup test employee in corporate tenant (e.g., ssec)
        with get_db_context() as db:
            tenant = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            if not tenant:
                tenant = db.query(Tenant).filter(Tenant.tenant_type == "corporate").first()
            self.assertIsNotNone(tenant, "Corporate tenant not found")
            self.tenant_id = tenant.id

            # Ensure SystemBranding exists with 15 min min_checkout_interval
            branding = db.query(SystemBranding).filter(SystemBranding.tenant_id == self.tenant_id).first()
            if not branding:
                branding = SystemBranding(
                    tenant_id=self.tenant_id,
                    min_checkout_interval_minutes=15,
                    cooldown_minutes=15,
                )
                db.add(branding)
            else:
                branding.min_checkout_interval_minutes = 15
                branding.cooldown_minutes = 15
            db.commit()

            # Create test student / employee
            emp = Student(
                tenant_id=self.tenant_id,
                name="Dup Test Employee",
                roll_number="EMP_DUP_TEST_001",
                department="Engineering",
                is_active=True,
                employment_status="ACTIVE",
            )
            db.add(emp)
            db.commit()
            db.refresh(emp)
            self.employee_id = emp.id

    def tearDown(self):
        self._cleanup_test_data()

    def _cleanup_test_data(self):
        with get_db_context() as db:
            test_rolls = ["EMP_DUP_TEST_001", "EMP_DUP_TEST_002", "EMP_DUP_TEST_003"]
            st_ids = [s.id for s in db.query(Student).filter(Student.roll_number.in_(test_rolls)).all()]
            if st_ids:
                db.query(AttendanceRecord).filter(AttendanceRecord.student_id.in_(st_ids)).delete(synchronize_session=False)
                db.query(Student).filter(Student.id.in_(st_ids)).delete(synchronize_session=False)
                db.commit()

    def test_rapid_consecutive_marks_prevent_duplicate_checkin(self):
        """Verify rapid consecutive calls to mark_attendance create only 1 check-in record."""
        # First call -> Check-In should succeed
        res1 = self.attendance_mgr.mark_attendance(
            student_id=self.employee_id,
            node_id="TEST-NODE-01",
            confidence_distance=0.35,
            tenant_id=self.tenant_id,
        )
        self.assertIsNotNone(res1)
        self.assertTrue(res1.get("attendance_logged"))
        self.assertEqual(res1.get("punch_type"), "CHECK_IN")

        # Immediate second call (within sliding debounce window) -> Suppressed
        res2 = self.attendance_mgr.mark_attendance(
            student_id=self.employee_id,
            node_id="TEST-NODE-01",
            confidence_distance=0.36,
            tenant_id=self.tenant_id,
        )
        self.assertIsNotNone(res2)
        self.assertFalse(res2.get("attendance_logged"))
        self.assertTrue(res2.get("cooldown_active"))

        # Immediate third call -> Suppressed
        res3 = self.attendance_mgr.mark_attendance(
            student_id=self.employee_id,
            node_id="TEST-NODE-01",
            confidence_distance=0.34,
            tenant_id=self.tenant_id,
        )
        self.assertIsNotNone(res3)
        self.assertFalse(res3.get("attendance_logged"))
        self.assertTrue(res3.get("cooldown_active"))

        # Verify only 1 record exists in DB
        with get_db_context() as db:
            records = db.query(AttendanceRecord).filter(
                AttendanceRecord.tenant_id == self.tenant_id,
                AttendanceRecord.student_id == self.employee_id,
            ).all()
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].punch_type, "CHECK_IN")
            self.assertIsNone(records[0].check_out_time)

    def test_multithreaded_concurrent_checkin_creates_single_record(self):
        """Verify concurrent threads attempting to check-in simultaneously create exactly 1 DB record."""
        results = []
        threads = []

        def worker():
            mgr = AttendanceManager()
            r = mgr.mark_attendance(
                student_id=self.employee_id,
                node_id="TEST-NODE-01",
                confidence_distance=0.35,
                tenant_id=self.tenant_id,
            )
            results.append(r)

        # Launch 5 concurrent threads
        for _ in range(5):
            t = threading.Thread(target=worker)
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Count successful check-ins
        logged_count = sum(1 for r in results if r and r.get("attendance_logged") is True)
        self.assertEqual(logged_count, 1, f"Expected exactly 1 successful check-in, got {logged_count}")

        # Verify exactly 1 record in database
        with get_db_context() as db:
            records = db.query(AttendanceRecord).filter(
                AttendanceRecord.tenant_id == self.tenant_id,
                AttendanceRecord.student_id == self.employee_id,
            ).all()
            self.assertEqual(len(records), 1)

    def test_checkout_interval_cooldown_prevents_premature_checkout(self):
        """Verify scans within min_checkout_interval are rejected as cooldown without creating new records."""
        base_time = datetime(2026, 9, 22, 10, 0, 0)

        # 1. Check-In at 10:00 AM
        res1 = self.attendance_mgr.mark_attendance(
            student_id=self.employee_id,
            node_id="TEST-NODE-01",
            confidence_distance=0.35,
            tenant_id=self.tenant_id,
            now_dt=base_time,
        )
        self.assertTrue(res1.get("attendance_logged"))
        self.assertEqual(res1.get("punch_type"), "CHECK_IN")

        # 2. Rescan 2 minutes later at 10:02 AM (tenant min_checkout_interval is 15 mins)
        res2 = self.attendance_mgr.mark_attendance(
            student_id=self.employee_id,
            node_id="TEST-NODE-01",
            confidence_distance=0.35,
            tenant_id=self.tenant_id,
            now_dt=base_time + timedelta(minutes=2),
        )
        self.assertFalse(res2.get("attendance_logged"))
        self.assertTrue(res2.get("cooldown_active"))
        self.assertIn("Check-In already logged", res2.get("message", ""))

        # 3. Rescan 14 minutes later at 10:14 AM (still within 15 min interval)
        res3 = self.attendance_mgr.mark_attendance(
            student_id=self.employee_id,
            node_id="TEST-NODE-01",
            confidence_distance=0.35,
            tenant_id=self.tenant_id,
            now_dt=base_time + timedelta(minutes=14),
        )
        self.assertFalse(res3.get("attendance_logged"))
        self.assertTrue(res3.get("cooldown_active"))

        # 4. Valid Check-Out at 10:30 AM (30 mins later, >= 15 min interval)
        res4 = self.attendance_mgr.mark_attendance(
            student_id=self.employee_id,
            node_id="TEST-NODE-01",
            confidence_distance=0.35,
            tenant_id=self.tenant_id,
            now_dt=base_time + timedelta(minutes=30),
        )
        self.assertTrue(res4.get("attendance_logged"))
        self.assertEqual(res4.get("punch_type"), "CHECK_OUT")
        self.assertEqual(res4.get("work_duration_minutes"), 30)

        # Verify DB still has exactly 1 record updated with check_out_time
        with get_db_context() as db:
            records = db.query(AttendanceRecord).filter(
                AttendanceRecord.tenant_id == self.tenant_id,
                AttendanceRecord.student_id == self.employee_id,
            ).all()
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].punch_type, "CHECK_OUT")
            self.assertIsNotNone(records[0].check_out_time)
            self.assertEqual(records[0].work_duration_minutes, 30)

    @patch("src.server.routes.api_nodes.face_engine")
    def test_single_frame_multi_detection_deduplication(self, mock_face_engine):
        """Verify if face_engine returns multiple bounding boxes for the same student in 1 frame, only 1 punch is logged."""
        # Mock face engine returning two bounding boxes for the same student in a single frame
        mock_face_engine.detect_and_recognize_faces.return_value = [
            {
                "is_match": True,
                "student_id": self.employee_id,
                "name": "Dup Test Employee",
                "roll_number": "EMP_DUP_TEST_001",
                "department": "Engineering",
                "user_role": "employee",
                "distance": 0.32,
                "threshold": 0.55,
                "confidence_pct": 92.0,
                "is_live": True,
                "liveness_score": 0.95,
                "liveness_status": "REAL",
                "temporal_confirmed": True,
                "temporal_status": "REAL",
                "temporal_frames": 3,
                "liveness_reasons": [],
                "box": {"top": 100, "right": 200, "bottom": 200, "left": 100},
            },
            {
                "is_match": True,
                "student_id": self.employee_id,
                "name": "Dup Test Employee",
                "roll_number": "EMP_DUP_TEST_001",
                "department": "Engineering",
                "user_role": "employee",
                "distance": 0.34,
                "threshold": 0.55,
                "confidence_pct": 91.0,
                "is_live": True,
                "liveness_score": 0.95,
                "liveness_status": "REAL",
                "temporal_confirmed": True,
                "temporal_status": "REAL",
                "temporal_frames": 3,
                "liveness_reasons": [],
                "box": {"top": 105, "right": 205, "bottom": 205, "left": 105},
            },
        ]

        # Create dummy JPEG image payload
        dummy_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
        dummy_img_bgr = np.zeros((480, 640, 3), dtype=np.uint8)

        client_with_auth = TestClient(app, cookies={
            "active_tenant_id": str(self.tenant_id),
            "active_role": "ADMIN",
        })

        with patch("src.server.routes.api_nodes.decode_image_bytes", return_value=dummy_img_bgr):
            response = client_with_auth.post(
                "/api/v1/nodes/frame",
                data={
                    "node_id": "DASHBOARD-CAMERA",
                    "location": "Live Terminal",
                    "tenant_id": str(self.tenant_id),
                },
                files={
                    "frame": ("frame.jpg", dummy_jpeg, "image/jpeg")
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        detections = data.get("detections", [])
        self.assertEqual(len(detections), 2)

        # First detection logged attendance
        self.assertTrue(detections[0].get("attendance_logged"))
        self.assertFalse(detections[0].get("cooldown_active"))

        # Second detection was deduplicated within the same frame
        self.assertFalse(detections[1].get("attendance_logged"))
        self.assertTrue(detections[1].get("cooldown_active"))
        self.assertEqual(detections[1].get("message"), "Duplicate detection in same frame ignored")

        # Verify only 1 record in database
        with get_db_context() as db:
            records = db.query(AttendanceRecord).filter(
                AttendanceRecord.tenant_id == self.tenant_id,
                AttendanceRecord.student_id == self.employee_id,
            ).all()
            self.assertEqual(len(records), 1)

    def test_broadcast_attendance_single_event_delivery(self):
        """Verify _broadcast_attendance dispatches exactly 1 event to each subscriber queue without duplication."""
        queue = self.attendance_mgr.subscribe()
        try:
            # Broadcast attendance log event
            self.attendance_mgr._broadcast_attendance(self.tenant_id, {
                "id": 99999,
                "student_name": "Test Broadcast",
                "roll_number": "EMP_DUP_TEST_001",
                "punch_type": "CHECK_IN",
            })

            # Queue should contain exactly 1 event
            self.assertEqual(queue.qsize(), 1, f"Expected 1 broadcast event in queue, found {queue.qsize()}")
            event = queue.get_nowait()
            self.assertEqual(event.get("type"), "ATTENDANCE_LOGGED")
            self.assertEqual(event.get("data", {}).get("id"), 99999)
            self.assertTrue(queue.empty())
        finally:
            self.attendance_mgr.unsubscribe(queue)

    def test_cold_cache_warmup_from_database(self):
        """Verify mark_attendance warms up cache from DB on cold start, blocking rapid successive scans."""
        base_time = datetime(2026, 9, 23, 10, 0, 0)
        # 1. First scan records Check-In
        res1 = self.attendance_mgr.mark_attendance(
            student_id=self.employee_id,
            node_id="TEST-NODE-01",
            confidence_distance=0.35,
            tenant_id=self.tenant_id,
            now_dt=base_time,
        )
        self.assertTrue(res1.get("attendance_logged"))

        # 2. Simulate server restart / memory wipe by clearing _last_logged_cache
        self.attendance_mgr._last_logged_cache.clear()
        self.assertNotIn((self.tenant_id, self.employee_id), self.attendance_mgr._last_logged_cache)

        # 3. Next scan 2 minutes later hits cold cache, should query DB, warm cache, and enforce corporate cooldown
        res2 = self.attendance_mgr.mark_attendance(
            student_id=self.employee_id,
            node_id="TEST-NODE-01",
            confidence_distance=0.35,
            tenant_id=self.tenant_id,
            now_dt=base_time + timedelta(minutes=2),
        )
        self.assertFalse(res2.get("attendance_logged"))
        self.assertTrue(res2.get("cooldown_active"))
        self.assertIn("Check-In already logged", res2.get("message", ""))


if __name__ == "__main__":
    unittest.main()
