import os
import sys
from pathlib import Path

# Setup path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Ensure DLL path for Anaconda OpenSSL
anaconda_bin = r"C:\ProgramData\Anaconda3\Library\bin"
if os.path.exists(anaconda_bin):
    try:
        os.add_dll_directory(anaconda_bin)
    except Exception:
        pass
    if anaconda_bin not in os.environ.get("PATH", ""):
        os.environ["PATH"] = anaconda_bin + os.pathsep + os.environ.get("PATH", "")

import unittest
import time
import numpy as np
import cv2
from fastapi.testclient import TestClient

from src.database.session import init_db, get_db_context, engine
from src.database.models import Student, FaceEncoding, AttendanceRecord, NodeDevice
from src.core.face_engine import FaceEngine
from src.core.attendance_manager import AttendanceManager
from src.server.app import app


class TestFaceAttendanceSystem(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Initialize database for tests."""
        init_db()
        cls.client = TestClient(app)

    def test_01_database_and_models(self):
        """Test database student registration and face encoding storage."""
        with get_db_context() as db:
            # Clean test student if exists
            old = db.query(Student).filter(Student.roll_number == "TEST-ROLL-001").first()
            if old:
                db.delete(old)
                db.commit()

            student = Student(
                roll_number="TEST-ROLL-001",
                name="Test Student Alpha",
                department="Computer Science",
                email="alpha@test.com",
            )
            db.add(student)
            db.flush()

            # Create synthetic 128-d vector
            synthetic_vector = np.random.rand(128).astype(np.float64)
            synthetic_vector /= np.linalg.norm(synthetic_vector)  # Unit vector

            encoding = FaceEncoding.from_numpy(
                student_id=student.id,
                vector=synthetic_vector,
                sample_angle="frontal",
            )
            db.add(encoding)
            db.commit()

            self.assertIsNotNone(student.id)
            self.assertEqual(len(student.encodings), 1)
            loaded_vec = student.encodings[0].get_numpy_vector()
            np.testing.assert_almost_equal(loaded_vec, synthetic_vector, decimal=5)
            print("[PASS] Test 1: Database ORM & Vector Serialization verified.")

    def test_02_face_engine_vector_matching(self):
        """Test in-memory FaceEngine vector cache and Euclidean distance matching."""
        engine = FaceEngine(distance_threshold=0.52)
        with get_db_context() as db:
            engine.initialize(db)

        self.assertGreater(len(engine._cached_metadata), 0)

        # Retrieve registered synthetic vector for TEST-ROLL-001
        with get_db_context() as db:
            student = db.query(Student).filter(Student.roll_number == "TEST-ROLL-001").first()
            target_vector = student.encodings[0].get_numpy_vector()

        # Test exact match (distance 0.0)
        match_result = engine.match_encoding(target_vector)
        self.assertTrue(match_result["is_match"])
        self.assertEqual(match_result["roll_number"], "TEST-ROLL-001")
        self.assertAlmostEqual(match_result["distance"], 0.0, places=3)
        self.assertEqual(match_result["confidence_pct"], 100.0)

        # Test slightly perturbed vector (distance ~0.2, still match)
        perturbed_vector = target_vector + (np.random.rand(128) * 0.02)
        match_perturbed = engine.match_encoding(perturbed_vector)
        self.assertTrue(match_perturbed["is_match"])
        self.assertEqual(match_perturbed["roll_number"], "TEST-ROLL-001")

        # Test orthogonal random vector (distance ~1.4, should be Unknown)
        random_vec = np.random.rand(128)
        random_vec /= np.linalg.norm(random_vec)
        match_unknown = engine.match_encoding(random_vec)
        self.assertFalse(match_unknown["is_match"])
        self.assertEqual(match_unknown["name"], "Unknown")
        print("[PASS] Test 2: In-Memory Vector Engine & Threshold Matching verified.")

    def test_03_attendance_deduplication_cooldown(self):
        """Test 5-minute deduplication window for preventing duplicate logs."""
        att_mgr = AttendanceManager(cooldown_seconds=300)

        with get_db_context() as db:
            student = db.query(Student).filter(Student.roll_number == "TEST-ROLL-001").first()
            student_id = student.id

        # First recognition -> Should LOG
        first_log = att_mgr.mark_attendance(
            student_id=student_id,
            node_id="NODE-TEST-101",
            confidence_distance=0.15,
        )
        self.assertIsNotNone(first_log)
        self.assertEqual(first_log["status"], "PRESENT")

        # Immediate second recognition -> Should SUPPRESS (cooldown active)
        second_log = att_mgr.mark_attendance(
            student_id=student_id,
            node_id="NODE-TEST-101",
            confidence_distance=0.16,
        )
        self.assertIsNone(second_log)
        print("[PASS] Test 3: Attendance Deduplication & Cooldown verified.")

    def test_04_api_endpoints(self):
        """Test FastAPI endpoints for health, stats, registration, logs, and export."""
        # 1. Health check
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "healthy")

        # 2. Stats summary
        res_stats = self.client.get("/api/v1/attendance/stats")
        self.assertEqual(res_stats.status_code, 200)
        self.assertIn("total_students", res_stats.json())

        # 3. Records retrieval
        res_records = self.client.get("/api/v1/attendance/records?roll_number=TEST-ROLL-001")
        self.assertEqual(res_records.status_code, 200)
        records = res_records.json()["records"]
        self.assertGreater(len(records), 0)

        # 4. CSV Export
        res_csv = self.client.get("/api/v1/attendance/export?export_format=csv")
        self.assertEqual(res_csv.status_code, 200)
        self.assertIn("text/csv", res_csv.headers["content-type"])
        self.assertIn("Roll Number", res_csv.text)

        # 5. Excel Export
        res_xlsx = self.client.get("/api/v1/attendance/export?export_format=xlsx")
        self.assertEqual(res_xlsx.status_code, 200)
        print("[PASS] Test 4: FastAPI REST API & Export Endpoints verified.")

    def test_05_batch_upload_validation(self):
        """Test batch upload endpoint constraints (requires exactly 3 photos)."""
        # Test with 2 photos (should fail validation)
        files_2 = [
            ("images", ("test1.jpg", b"fake_image_bytes_1", "image/jpeg")),
            ("images", ("test2.jpg", b"fake_image_bytes_2", "image/jpeg")),
        ]
        data = {
            "roll_number": "TEST-BATCH-001",
            "name": "Batch Test Student",
            "department": "Computer Science",
        }
        res_fail = self.client.post("/api/v1/enroll/batch-upload", data=data, files=files_2)
        self.assertEqual(res_fail.status_code, 400)
        self.assertIn("Exactly 3 photos are required", res_fail.json()["detail"])

        # Test with 4 photos (should also fail)
        files_4 = [
            ("images", (f"test{i}.jpg", b"fake_image_bytes", "image/jpeg"))
            for i in range(4)
        ]
        res_fail_4 = self.client.post("/api/v1/enroll/batch-upload", data=data, files=files_4)
        self.assertEqual(res_fail_4.status_code, 400)
        print("[PASS] Test 5: Batch Upload 3-photo strict validation verified.")

    def test_06_liveness_detector(self):
        """Test LivenessDetector FFT texture, chromatic skin analysis, and flatness heuristics."""
        from src.core.liveness_detector import LivenessDetector

        detector = LivenessDetector(threshold=0.65)

        # 1. Test flat uniform color patch (Simulated blank screen / bad photo)
        flat_image = np.ones((200, 200, 3), dtype=np.uint8) * 120
        box = {"top": 10, "right": 190, "bottom": 190, "left": 10}
        res_flat = detector.evaluate_liveness(flat_image, box)
        self.assertFalse(res_flat["is_live"])
        self.assertEqual(res_flat["status"], "SPOOF_SUSPECTED")
        self.assertLess(res_flat["score"], 0.65)

        # 2. Test natural skin tone image with organic gradient
        natural_face = np.zeros((200, 200, 3), dtype=np.uint8)
        natural_face[:, :, 0] = 110
        natural_face[:, :, 1] = 145
        natural_face[:, :, 2] = 205
        noise = np.random.normal(0, 4, (200, 200)).astype(np.float32)
        noise = cv2.GaussianBlur(noise, (5, 5), 1.5)
        natural_face = np.clip(natural_face + noise[:, :, None], 0, 255).astype(np.uint8)
        
        res_natural = detector.evaluate_liveness(natural_face, box)
        self.assertTrue(res_natural["is_live"])
        self.assertEqual(res_natural["status"], "REAL")
        self.assertGreaterEqual(res_natural["score"], 0.65)
        print("[PASS] Test 6: LivenessDetector Spectral & Chromatic Anti-Spoofing verified.")

    def test_07_temporal_tracker(self):
        """Test 5-frame temporal motion tracking, node isolation, and static spoof rejection."""
        from src.core.liveness_detector import TemporalMotionTracker

        tracker = TemporalMotionTracker(confirmation_frames=5, max_idle_seconds=2.0)
        box = {"top": 50, "right": 150, "bottom": 150, "left": 50}

        # Frame 1 to 4: Real face detected with organic micro-movement -> should be in VERIFYING (1/5 to 4/5)
        for i in range(1, 5):
            box_i = {"top": 50 + (i % 2), "right": 150 + (i % 2), "bottom": 150 + (i % 2), "left": 50 + (i % 2)}
            confirmed, frames, status = tracker.update_track(student_id=999, face_box=box_i, is_single_frame_live=True, node_id="NODE-A")
            self.assertFalse(confirmed)
            self.assertEqual(frames, i)
            self.assertIn(f"{i}/5", status)

        # Frame 5: Real face with micro-displacement -> should CONFIRM (5/5)
        box5 = {"top": 51, "right": 151, "bottom": 151, "left": 51}
        confirmed_5, f5, status_5 = tracker.update_track(student_id=999, face_box=box5, is_single_frame_live=True, node_id="NODE-A")
        self.assertTrue(confirmed_5)
        self.assertEqual(f5, 5)
        self.assertEqual(status_5, "REAL")

        # Frame 6: Spoof attack injected -> should immediately invalidate track
        confirmed_6, f6, status_6 = tracker.update_track(student_id=999, face_box=box5, is_single_frame_live=False, node_id="NODE-A")
        self.assertFalse(confirmed_6)
        self.assertEqual(f6, 0)
        self.assertEqual(status_6, "SPOOF_DETECTED")

        # Node Isolation Test: NODE-B should have independent track for same student
        confirmed_b, fb, status_b = tracker.update_track(student_id=999, face_box=box, is_single_frame_live=True, node_id="NODE-B")
        self.assertFalse(confirmed_b)
        self.assertEqual(fb, 1)
        self.assertIn("1/5", status_b)

        # Static Freeze Photo Rejection Test: 5 frames with 0.0px variance
        freeze_tracker = TemporalMotionTracker(confirmation_frames=5, max_idle_seconds=2.0)
        frozen_box = {"top": 100, "right": 200, "bottom": 200, "left": 100}
        for _ in range(4):
            freeze_tracker.update_track(student_id=888, face_box=frozen_box, is_single_frame_live=True)
        # 5th frame: still exactly frozen with 0.0px motion -> should detect spoof freeze
        conf_freeze, _, stat_freeze = freeze_tracker.update_track(student_id=888, face_box=frozen_box, is_single_frame_live=True)
        self.assertFalse(conf_freeze)
        self.assertEqual(stat_freeze, "SPOOF_DETECTED")
        print("[PASS] Test 7: 5-Frame Temporal Micro-Motion & Static Freeze Defense verified.")

    def test_08_edit_student_profile(self):
        """Test PUT /api/v1/enroll/student/{student_id} endpoint."""
        with get_db_context() as db:
            student = db.query(Student).filter(Student.roll_number == "TEST-ROLL-001").first()
            self.assertIsNotNone(student)
            student_id = student.id

        # 1. Successful profile update
        update_data = {
            "name": "Updated Test Alpha",
            "roll_number": "TEST-ROLL-001-MOD",
            "department": "Artificial Intelligence",
            "email": "alpha_updated@test.com",
        }
        res = self.client.put(f"/api/v1/enroll/student/{student_id}", json=update_data)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["student"]["name"], "Updated Test Alpha")
        self.assertEqual(res.json()["student"]["department"], "Artificial Intelligence")

        # 2. Revert back roll number
        update_data["roll_number"] = "TEST-ROLL-001"
        res_revert = self.client.put(f"/api/v1/enroll/student/{student_id}", json=update_data)
        self.assertEqual(res_revert.status_code, 200)

        # 3. Invalid student ID
        res_404 = self.client.put("/api/v1/enroll/student/99999", json=update_data)
        self.assertEqual(res_404.status_code, 404)
        print("[PASS] Test 8: Student Profile Editing & Validation verified.")

    def test_09_get_and_update_photos_validation(self):
        """Test GET and POST photo update validation endpoints."""
        with get_db_context() as db:
            student = db.query(Student).filter(Student.roll_number == "TEST-ROLL-001").first()
            student_id = student.id

        # 1. GET student details with photo array
        res_get = self.client.get(f"/api/v1/enroll/student/{student_id}")
        self.assertEqual(res_get.status_code, 200)
        self.assertIn("photos", res_get.json()["student"])

        # 2. Update photos with fewer than 3 images (should fail validation)
        files_2 = [
            ("images", ("p1.jpg", b"fake_bytes_1", "image/jpeg")),
            ("images", ("p2.jpg", b"fake_bytes_2", "image/jpeg")),
        ]
        res_fail = self.client.post(f"/api/v1/enroll/student/{student_id}/update-photos", files=files_2)
        self.assertEqual(res_fail.status_code, 400)
        self.assertIn("Exactly 3 photos are required", res_fail.json()["detail"])
        print("[PASS] Test 9: Reference Photo Viewer & Update Validation verified.")

    def test_10_mobile_capture_view(self):
        """Test GET /mobile-capture HTML view rendering."""
        res = self.client.get("/mobile-capture")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Mobile Capture Node", res.text)
        self.assertIn("NODE-MOBILE-CAMERA", res.text)
        print("[PASS] Test 10: Mobile Capture Web View verified.")

    def test_11_mobile_frame_ingestion(self):
        """Test POST /api/v1/nodes/frame with mobile node metadata."""
        # Create small test frame
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        _, buffer = cv2.imencode(".jpg", dummy_frame)

        files = {"frame": ("mobile_frame.jpg", buffer.tobytes(), "image/jpeg")}
        data = {"node_id": "NODE-MOBILE-CAMERA", "location": "Smartphone Node"}

        res = self.client.post("/api/v1/nodes/frame", files=files, data=data)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["node_id"], "NODE-MOBILE-CAMERA")
        print("[PASS] Test 11: Mobile Frame Ingestion & Node Ingestion verified.")

    def test_12_manual_override_audit(self):
        """Test POST /api/v1/attendance/manual-override endpoint and audit fields."""
        with get_db_context() as db:
            student = db.query(Student).first()
            self.assertIsNotNone(student)
            student_id = student.id

        payload = {
            "student_id": student_id,
            "timestamp": "2026-09-02 10:30:00",
            "reason": "Medical Leave Certificate Approved",
            "override_by": "Dr. Smith (Dean)",
        }

        res = self.client.post("/api/v1/attendance/manual-override", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(data["record"]["is_manual_override"])
        self.assertEqual(data["record"]["override_reason"], "Medical Leave Certificate Approved")
        self.assertEqual(data["record"]["override_by"], "Dr. Smith (Dean)")

        # Verify record exists in GET /records with is_override=true
        res_rec = self.client.get("/api/v1/attendance/records?is_override=true")
        self.assertEqual(res_rec.status_code, 200)
        self.assertGreaterEqual(len(res_rec.json()["records"]), 1)
        self.assertTrue(res_rec.json()["records"][0]["is_manual_override"])
        print("[PASS] Test 12: Biometric Fallback / Manual Override & Audit Logging verified.")

    def test_13_analytics_and_defaulters(self):
        """Test GET /api/v1/attendance/analytics with configurable threshold."""
        # 1. Standard 75% threshold
        res_75 = self.client.get("/api/v1/attendance/analytics?defaulter_threshold=75.0&days=7")
        self.assertEqual(res_75.status_code, 200)
        data_75 = res_75.json()
        self.assertEqual(data_75["status"], "success")
        self.assertIn("headcount", data_75)
        self.assertIn("daily_trends", data_75)
        self.assertIn("departments", data_75)
        self.assertIn("defaulters", data_75)
        self.assertEqual(data_75["defaulter_threshold"], 75.0)

        # 2. Configurable 50% threshold
        res_50 = self.client.get("/api/v1/attendance/analytics?defaulter_threshold=50.0")
        self.assertEqual(res_50.status_code, 200)
        self.assertEqual(res_50.json()["defaulter_threshold"], 50.0)
        print("[PASS] Test 13: Institutional Analytics & Configurable Defaulters verified.")

    def test_14_compliance_export(self):
        """Test GET /api/v1/attendance/export-compliance endpoint."""
        res_csv = self.client.get("/api/v1/attendance/export-compliance?export_format=csv&defaulter_threshold=75.0")
        self.assertEqual(res_csv.status_code, 200)
        self.assertIn("text/csv", res_csv.headers["content-type"])
        self.assertIn("Student ID / Roll", res_csv.text)

        res_xlsx = self.client.get("/api/v1/attendance/export-compliance?export_format=xlsx&defaulter_threshold=75.0")
        self.assertEqual(res_xlsx.status_code, 200)
        self.assertIn("spreadsheetml.sheet", res_xlsx.headers["content-type"])
        print("[PASS] Test 14: Institutional Compliance Export (CSV & Excel) verified.")

    def test_15_role_based_enrollment(self):
        """Test role classification (teacher/staff/student) at registration."""
        unique_roll = f"FACULTY-{int(time.time())}"
        payload = {
            "roll_number": unique_roll,
            "name": "Prof. Charles Xavier",
            "department": "Artificial Intelligence",
            "email": "charles.xavier@university.edu",
            "user_role": "teacher",
            "class_semester": "Faculty Wing B",
        }

        res = self.client.post("/api/v1/enroll/student", json=payload)
        self.assertEqual(res.status_code, 200)
        student = res.json()["student"]
        self.assertEqual(student["user_role"], "teacher")
        self.assertEqual(student["class_semester"], "Faculty Wing B")

        # Verify stats endpoint properly separates students
        res_stats = self.client.get("/api/v1/attendance/stats")
        self.assertEqual(res_stats.status_code, 200)
        stats = res_stats.json()
        self.assertGreaterEqual(stats["total_all_users"], stats["total_students"])
        print("[PASS] Test 15: Role-Based User Classification & Stats Exclusion verified.")

    def test_16_settings_view_and_themes(self):
        """Test GET /settings view rendering and multi-theme components."""
        res = self.client.get("/settings")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Visual Theme Personalization", res.text)
        self.assertIn("Clean Minimalist Light", res.text)
        self.assertIn("Executive Midnight Dark", res.text)
        self.assertIn("Warm Academic", res.text)
        self.assertIn("Institutional Attendance Parameters", res.text)
        self.assertIn("btnQuickThemeToggle", res.text)
        print("[PASS] Test 16: Multi-Theme Engine & Settings Menu View verified.")

    def test_17_institutional_branding(self):
        """Test institutional white-labeling API, text updates, and logo uploads."""
        # 1. GET branding defaults
        res_get = self.client.get("/api/v1/branding")
        self.assertEqual(res_get.status_code, 200)
        self.assertIn("branding", res_get.json())

        # 2. POST update text and colors
        update_payload = {
            "institution_name": "MIT Vision & Robotics Lab",
            "short_code": "MIT-ROBO",
            "tagline": "Real-time Autonomous Edge Biometrics",
            "primary_accent_color": "#0ea5e9",
            "header_badge_text": "Robotics Center",
            "contact_email": "admin@mit.edu",
        }
        res_post = self.client.post("/api/v1/branding", json=update_payload)
        self.assertEqual(res_post.status_code, 200)
        branding = res_post.json()["branding"]
        self.assertEqual(branding["institution_name"], "MIT Vision & Robotics Lab")
        self.assertEqual(branding["short_code"], "MIT-ROBO")
        self.assertEqual(branding["primary_accent_color"], "#0ea5e9")

        # 3. Upload dummy logo file
        dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
        _, img_buf = cv2.imencode(".png", dummy_img)
        files = {"logo": ("campus_logo.png", img_buf.tobytes(), "image/png")}

        res_logo = self.client.post("/api/v1/branding/logo", files=files)
        self.assertEqual(res_logo.status_code, 200)
        data_logo = res_logo.json()
        self.assertIsNotNone(data_logo["branding"]["logo_url"])
        self.assertTrue(data_logo["branding"]["logo_url"].startswith("/data/branding/"))

        # 4. Reset logo
        res_del = self.client.delete("/api/v1/branding/logo")
        self.assertEqual(res_del.status_code, 200)
        self.assertIsNone(res_del.json()["branding"]["logo_url"])
        print("[PASS] Test 17: Institutional White-Labeling, Custom Branding & Logo Engine verified.")


if __name__ == "__main__":
    unittest.main()
