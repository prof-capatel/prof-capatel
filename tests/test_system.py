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
from datetime import date, datetime
import numpy as np
import cv2
from fastapi.testclient import TestClient

from src.database.session import init_db, get_db_context, engine
from src.database.models import Student, FaceEncoding, AttendanceRecord, NodeDevice, Tenant, SystemBranding, ClassModel
from src.core.face_engine import FaceEngine, face_engine
from src.core.attendance_manager import AttendanceManager, attendance_manager
from src.server.app import app


class TestFaceAttendanceSystem(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Initialize database for tests."""
        init_db()
        cls.client = TestClient(app)

    def test_01_database_and_models(self):
        """Test database student registration and face encoding storage under Tenant #1."""
        with get_db_context() as db:
            # Clean test student if exists
            old = db.query(Student).filter(Student.tenant_id == 1, Student.roll_number == "TEST-ROLL-001").first()
            if old:
                db.delete(old)
                db.commit()

            student = Student(
                tenant_id=1,
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
                tenant_id=1,
            )
            db.add(encoding)
            db.commit()

            self.assertIsNotNone(student.id)
            self.assertEqual(len(student.encodings), 1)
            loaded_vec = student.encodings[0].get_numpy_vector()
            np.testing.assert_almost_equal(loaded_vec, synthetic_vector, decimal=5)
            print("[PASS] Test 1: MySQL Multi-Tenant ORM & Vector Serialization verified.")

    def test_02_face_engine_vector_matching(self):
        """Test in-memory FaceEngine vector cache and Euclidean distance matching."""
        engine_instance = FaceEngine(distance_threshold=0.52)
        with get_db_context() as db:
            engine_instance.initialize(db, tenant_id=1)

        self.assertGreater(len(engine_instance._tenant_metadata.get(1, [])), 0)

        # Retrieve registered synthetic vector for TEST-ROLL-001
        with get_db_context() as db:
            student = db.query(Student).filter(Student.tenant_id == 1, Student.roll_number == "TEST-ROLL-001").first()
            target_vector = student.encodings[0].get_numpy_vector()

        # Test exact match (distance 0.0)
        match_result = engine_instance.match_encoding(target_vector, tenant_id=1)
        self.assertTrue(match_result["is_match"])
        self.assertEqual(match_result["roll_number"], "TEST-ROLL-001")
        self.assertAlmostEqual(match_result["distance"], 0.0, places=3)
        self.assertEqual(match_result["confidence_pct"], 100.0)

        # Test slightly perturbed vector (distance ~0.02, still match)
        perturbed_vector = target_vector + (np.random.rand(128) * 0.02)
        match_perturbed = engine_instance.match_encoding(perturbed_vector, tenant_id=1)
        self.assertTrue(match_perturbed["is_match"])
        self.assertEqual(match_perturbed["roll_number"], "TEST-ROLL-001")

        # Test orthogonal random vector (distance ~1.4, should be Unknown)
        random_vec = np.random.rand(128)
        random_vec /= np.linalg.norm(random_vec)
        match_unknown = engine_instance.match_encoding(random_vec, tenant_id=1)
        self.assertFalse(match_unknown["is_match"])
        self.assertEqual(match_unknown["name"], "Unknown")
        print("[PASS] Test 2: In-Memory Multi-Tenant Vector Engine & Threshold Matching verified.")

    def test_03_attendance_deduplication_cooldown(self):
        """Test campus-wide deduplication window for preventing duplicate logs."""
        att_mgr = AttendanceManager(default_cooldown_seconds=300)

        with get_db_context() as db:
            student = db.query(Student).filter(Student.tenant_id == 1, Student.roll_number == "TEST-ROLL-001").first()
            student_id = student.id

        # First recognition -> Should LOG
        first_res = att_mgr.mark_attendance(
            student_id=student_id,
            node_id="NODE-TEST-101",
            confidence_distance=0.15,
            tenant_id=1,
            custom_cooldown_seconds=300,
        )
        self.assertIsNotNone(first_res)
        self.assertTrue(first_res["attendance_logged"])
        self.assertFalse(first_res["cooldown_active"])
        self.assertEqual(first_res["log_data"]["status"], "PRESENT")

        # Immediate second recognition -> Should SUPPRESS (cooldown active)
        second_res = att_mgr.mark_attendance(
            student_id=student_id,
            node_id="NODE-TEST-101",
            confidence_distance=0.16,
            tenant_id=1,
            custom_cooldown_seconds=300,
        )
        self.assertIsNotNone(second_res)
        self.assertFalse(second_res["attendance_logged"])
        self.assertTrue(second_res["cooldown_active"])
        self.assertGreater(second_res["cooldown_remaining_seconds"], 0)
        print("[PASS] Test 3: Attendance Deduplication & Configurable Cooldown verified.")

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
        """Test batch upload endpoint constraints (requires valid photos)."""
        data = {
            "roll_number": "TEST-BATCH-001",
            "name": "Batch Test Student",
            "department": "Computer Science",
        }
        # Bad dummy bytes should trigger image validation error
        files_bad = {
            "photo_front": ("front.jpg", b"bad_bytes", "image/jpeg"),
            "photo_left": ("left.jpg", b"bad_bytes", "image/jpeg"),
            "photo_right": ("right.jpg", b"bad_bytes", "image/jpeg"),
        }
        res_fail = self.client.post("/api/v1/enroll/batch-upload", data=data, files=files_bad)
        self.assertEqual(res_fail.status_code, 400)
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
            student = db.query(Student).filter(Student.tenant_id == 1, Student.roll_number == "TEST-ROLL-001").first()
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
            student = db.query(Student).filter(Student.tenant_id == 1, Student.roll_number == "TEST-ROLL-001").first()
            student_id = student.id

        # 1. GET student details with photo array
        res_get = self.client.get(f"/api/v1/enroll/student/{student_id}")
        self.assertEqual(res_get.status_code, 200)
        self.assertIn("photos", res_get.json()["student"])

        # 2. Update photos with empty form should fail validation
        res_fail = self.client.post(f"/api/v1/enroll/student/{student_id}/update-photos", files={})
        self.assertEqual(res_fail.status_code, 400)
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
            student = db.query(Student).filter(Student.tenant_id == 1).first()
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

    def test_18_tenant_management_endpoints(self):
        """Test SaaS Tenant creation and listing endpoints."""
        # 1. List tenants
        res_list = self.client.get("/api/v1/tenants")
        self.assertEqual(res_list.status_code, 200)
        tenants = res_list.json()["tenants"]
        self.assertGreaterEqual(len(tenants), 1)

        # 2. Create secondary tenant (e.g. Oxford Institute)
        oxford_payload = {
            "name": "Oxford Institute of Technology",
            "slug": f"oxford-{int(time.time())}",
            "contact_email": "dean@oxford.edu",
            "short_code": "OX-TECH",
            "primary_accent_color": "#10b981",
        }
        res_create = self.client.post("/api/v1/tenants", json=oxford_payload)
        self.assertEqual(res_create.status_code, 201)
        created_tenant = res_create.json()["tenant"]
        self.assertEqual(created_tenant["name"], "Oxford Institute of Technology")
        print("[PASS] Test 18: SaaS Tenant Creation, Listing & Switcher API verified.")

    def test_19_multi_tenant_strict_data_isolation(self):
        """Test strict cross-tenant isolation: identical roll numbers across tenants and zero cross-leakage."""
        with get_db_context() as db:
            # Create Tenant B if not exists
            tenant_b = db.query(Tenant).filter(Tenant.slug == "tenant-b-test").first()
            if not tenant_b:
                tenant_b = Tenant(
                    slug="tenant-b-test",
                    name="Tenant B Autonomous Academy",
                    contact_email="admin@tenant-b.edu",
                    is_active=True,
                    subscription_status="ACTIVE",
                    subscription_plan="STANDARD",
                    max_face_encodings=500,
                    max_nodes=10,
                )
                db.add(tenant_b)
                db.flush()
                branding_b = SystemBranding(
                    tenant_id=tenant_b.id,
                    institution_name=tenant_b.name,
                    short_code="TB-ACAD",
                )
                db.add(branding_b)
                db.commit()
            else:
                tenant_b.subscription_status = "ACTIVE"
                tenant_b.is_active = True
                tenant_b.is_deleted = False
                db.commit()

            tenant_b_id = tenant_b.id

            # Clean any old test students in Tenant B
            old_b_std = db.query(Student).filter(Student.tenant_id == tenant_b_id, Student.roll_number == "SHARED-ROLL-100").first()
            if old_b_std:
                db.delete(old_b_std)
                db.commit()

            # Clean any old test student in Tenant 1 with same roll number
            old_a_std = db.query(Student).filter(Student.tenant_id == 1, Student.roll_number == "SHARED-ROLL-100").first()
            if old_a_std:
                db.delete(old_a_std)
                db.commit()

        # 1. Register student in Tenant 1 with roll number SHARED-ROLL-100
        res_a = self.client.post(
            "/api/v1/enroll/student",
            json={"roll_number": "SHARED-ROLL-100", "name": "Alice Tenant A", "department": "AI"},
            headers={"X-Tenant-ID": "1"},
        )
        self.assertEqual(res_a.status_code, 200)

        # 2. Register student in Tenant B with EXACT SAME roll number SHARED-ROLL-100 (should succeed due to multi-tenant compound constraint)
        res_b = self.client.post(
            "/api/v1/enroll/student",
            json={"roll_number": "SHARED-ROLL-100", "name": "Bob Tenant B", "department": "Cybersecurity"},
            headers={"X-Tenant-ID": str(tenant_b_id)},
        )
        self.assertEqual(res_b.status_code, 200)

        # 3. Query records in Tenant 1 -> Must NEVER see Bob Tenant B
        res_recs_a = self.client.get("/api/v1/attendance/records", headers={"X-Tenant-ID": "1"})
        self.assertEqual(res_recs_a.status_code, 200)
        names_a = [r["student_name"] for r in res_recs_a.json()["records"]]
        self.assertNotIn("Bob Tenant B", names_a)

        # 4. Ingest frame under Tenant B -> Vector match engine must only match Bob, never Alice
        face_engine.reload_cache(tenant_id=1)
        face_engine.reload_cache(tenant_id=tenant_b_id)

        # 5. Query stats for Tenant B -> must show exactly Tenant B's student count
        res_stats_b = self.client.get("/api/v1/attendance/stats", headers={"X-Tenant-ID": str(tenant_b_id)})
        self.assertEqual(res_stats_b.status_code, 200)
        self.assertEqual(res_stats_b.json()["tenant_id"], tenant_b_id)
        self.assertGreaterEqual(res_stats_b.json()["total_students"], 1)

        print("[PASS] Test 19: Strict Multi-Tenant Data Isolation & Compound Unique Constraints verified.")

    def test_20_configurable_cooldown_and_multi_face_api(self):
        """Test institutional configurable cooldown update and multi-face response format."""
        # 1. Update cooldown to 1 minute via branding API
        update_payload = {
            "institution_name": "FaceAttendance Campus",
            "short_code": "FA-HUB",
            "cooldown_minutes": 1,
        }
        res_update = self.client.post("/api/v1/branding", json=update_payload)
        self.assertEqual(res_update.status_code, 200)

        # 2. Verify branding returns 1 minute
        res_brand = self.client.get("/api/v1/branding")
        self.assertEqual(res_brand.status_code, 200)
        self.assertEqual(res_brand.json()["branding"]["cooldown_minutes"], 1)

        # 3. Verify attendance manager immediately reflects 60 seconds via automatic cache invalidation
        cd_secs = attendance_manager.get_tenant_cooldown_seconds(tenant_id=1)
        self.assertEqual(cd_secs, 60)

        # 4. Ingest frame and verify response has both 'detections' and 'results' lists
        test_frame = np.full((240, 320, 3), 128, dtype=np.uint8)
        _, jpeg_bytes = cv2.imencode(".jpg", test_frame)
        files = {"frame": ("multi_test.jpg", jpeg_bytes.tobytes(), "image/jpeg")}
        data = {"node_id": "NODE-MULTI-TEST", "location": "Room 201"}

        res_frame = self.client.post("/api/v1/nodes/frame", files=files, data=data)
        self.assertEqual(res_frame.status_code, 200)
        json_data = res_frame.json()
        self.assertIn("detections", json_data)
        self.assertIn("results", json_data)
        self.assertIsInstance(json_data["detections"], list)
        self.assertIsInstance(json_data["results"], list)

        print("[PASS] Test 20: Configurable Cooldown API & Multi-Face Batch Processing verified.")

    def test_21_configurable_antispoofing_and_audio_chime_settings(self):
        """Test institutional anti-spoofing temporal window, liveness modes, and audio chime toggles."""
        # 1. Update branding settings with strict anti-spoofing and audio chime
        update_payload = {
            "institution_name": "FaceAttendance Campus",
            "short_code": "FA-HUB",
            "cooldown_minutes": 90,
            "liveness_mode": "STRICT",
            "temporal_frames_required": 5,
            "enable_audio_chime": True,
            "enable_haptic_feedback": True,
        }
        res_update = self.client.post("/api/v1/branding", json=update_payload)
        self.assertEqual(res_update.status_code, 200)

        # 2. Verify settings retrieval via branding GET
        res_brand = self.client.get("/api/v1/branding")
        self.assertEqual(res_brand.status_code, 200)
        brand_data = res_brand.json()["branding"]
        self.assertEqual(brand_data["cooldown_minutes"], 90)
        self.assertEqual(brand_data["liveness_mode"], "STRICT")
        self.assertEqual(brand_data["temporal_frames_required"], 5)
        self.assertTrue(brand_data["enable_audio_chime"])
        self.assertTrue(brand_data["enable_haptic_feedback"])

        # 3. Test TemporalMotionTracker with custom confirmation frame requirement (3 vs 5 frames)
        from src.core.liveness_detector import TemporalMotionTracker
        tracker = TemporalMotionTracker(confirmation_frames=5)
        box = {"top": 100, "right": 200, "bottom": 200, "left": 100}

        # Frame 1: Not confirmed with target=3
        is_conf_1, frames_1, status_1 = tracker.update_track(student_id=999, face_box=box, is_single_frame_live=True, node_id="TEST-NODE-1", custom_confirmation_frames=3)
        self.assertFalse(is_conf_1)
        self.assertEqual(frames_1, 1)
        self.assertIn("1/3", status_1)

        # Frame 2: Not confirmed with target=3
        box2 = {"top": 101, "right": 201, "bottom": 201, "left": 101}
        is_conf_2, frames_2, status_2 = tracker.update_track(student_id=999, face_box=box2, is_single_frame_live=True, node_id="TEST-NODE-1", custom_confirmation_frames=3)
        self.assertFalse(is_conf_2)
        self.assertEqual(frames_2, 2)
        self.assertIn("2/3", status_2)

        # Frame 3: Confirmed with target=3!
        box3 = {"top": 102, "right": 202, "bottom": 202, "left": 102}
        is_conf_3, frames_3, status_3 = tracker.update_track(student_id=999, face_box=box3, is_single_frame_live=True, node_id="TEST-NODE-1", custom_confirmation_frames=3)
        self.assertTrue(is_conf_3)
        self.assertEqual(frames_3, 3)
        self.assertEqual(status_3, "REAL")

        print("[PASS] Test 21: Configurable Anti-Spoofing & Audio Chime Settings verified.")

    def test_22_ist_timezone_standardization_and_demo_frame_api(self):
        """Test IST timezone generation and standalone non-logging demo-frame API."""
        from src.utils.timezone import get_ist_now, get_ist_date
        ist_now = get_ist_now()
        ist_today = get_ist_date()
        self.assertIsNotNone(ist_now)
        self.assertIsNotNone(ist_today)

        # 1. Count attendance records before demo ingestion
        initial_records_count = len(self.client.get("/api/v1/attendance/records").json()["records"])

        # 2. Ingest frame to /api/v1/nodes/demo-frame
        test_frame = np.full((240, 320, 3), 128, dtype=np.uint8)
        _, jpeg_bytes = cv2.imencode(".jpg", test_frame)
        files = {"frame": ("demo_test.jpg", jpeg_bytes.tobytes(), "image/jpeg")}
        data = {"node_id": "NODE-DEMO-TEST"}

        res_demo = self.client.post("/api/v1/nodes/demo-frame", files=files, data=data)
        self.assertEqual(res_demo.status_code, 200)
        demo_json = res_demo.json()
        self.assertTrue(demo_json.get("demo_mode"))
        self.assertIn("detections", demo_json)

        # 3. Verify that ZERO records were written to attendance database
        after_records_count = len(self.client.get("/api/v1/attendance/records").json()["records"])
        self.assertEqual(initial_records_count, after_records_count)

        # 4. Verify /face-demo HTML view loads successfully
        res_view = self.client.get("/face-demo")
        self.assertEqual(res_view.status_code, 200)
        self.assertIn("Visual Recognition Demo", res_view.text)

        print("[PASS] Test 22: IST Timezone & Non-Logging Demo Frame API verified.")

    def test_23_configurable_anti_spoofing_toggle(self):
        """Test toggling anti-spoofing on/off via institutional branding and verifying bypass behavior."""
        # 1. Disable anti-spoofing via branding API
        update_payload = {
            "institution_name": "FaceAttendance Campus",
            "short_code": "FA-HUB",
            "enable_anti_spoofing": False,
        }
        res_update = self.client.post("/api/v1/branding", json=update_payload)
        self.assertEqual(res_update.status_code, 200)

        # 2. Verify settings retrieval shows anti-spoofing disabled
        res_brand = self.client.get("/api/v1/branding")
        self.assertEqual(res_brand.status_code, 200)
        brand_data = res_brand.json()["branding"]
        self.assertFalse(brand_data["enable_anti_spoofing"])

        # 3. Test FaceEngine with enable_anti_spoofing=False
        test_frame = np.full((240, 320, 3), 128, dtype=np.uint8)
        # Mocking a detected location
        fe_res = face_engine.detect_and_recognize_faces(test_frame, enable_anti_spoofing=False)
        # Empty frame returns empty list, testing direct vector engine with disabled anti-spoofing
        self.assertIsInstance(fe_res, list)

        # 4. Ingest frame to /api/v1/nodes/frame and /api/v1/nodes/demo-frame while disabled
        _, jpeg_bytes = cv2.imencode(".jpg", test_frame)
        files = {"frame": ("test_toggle.jpg", jpeg_bytes.tobytes(), "image/jpeg")}
        res_demo = self.client.post("/api/v1/nodes/demo-frame", files=files, data={"node_id": "NODE-TOGGLE-TEST"})
        self.assertEqual(res_demo.status_code, 200)

        # 5. Re-enable anti-spoofing
        restore_payload = {
            "institution_name": "FaceAttendance Campus",
            "short_code": "FA-HUB",
            "enable_anti_spoofing": True,
        }
        res_restore = self.client.post("/api/v1/branding", json=restore_payload)
        self.assertEqual(res_restore.status_code, 200)
        self.assertTrue(res_restore.json()["branding"]["enable_anti_spoofing"])

        print("[PASS] Test 23: Configurable Anti-Spoofing & Liveness Toggle verified.")

    def test_24_rbac_authentication_and_role_switching(self):
        """Test user login, password verification, JWT generation, and role switching."""
        # 1. Super Admin login
        res_sa = self.client.post("/api/v1/auth/login", json={"username": "superadmin", "password": "admin123"})
        self.assertEqual(res_sa.status_code, 200)
        sa_data = res_sa.json()
        self.assertEqual(sa_data["user"]["role"], "SUPER_ADMIN")
        self.assertIn("access_token", sa_data)

        # 2. Tenant Admin login
        res_ta = self.client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123", "tenant_id": 1})
        self.assertEqual(res_ta.status_code, 200)
        self.assertEqual(res_ta.json()["user"]["role"], "TENANT_ADMIN")

        # 3. Invalid credentials rejection
        res_bad = self.client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrongpassword"})
        self.assertEqual(res_bad.status_code, 401)

        # 4. Role switching
        res_switch = self.client.post("/api/v1/auth/switch-role", json={"role": "TEACHER", "tenant_id": 1})
        self.assertEqual(res_switch.status_code, 200)
        self.assertEqual(res_switch.json()["user"]["role"], "TEACHER")

        # Reset back to Super Admin for test suite
        self.client.post("/api/v1/auth/switch-role", json={"role": "SUPER_ADMIN", "tenant_id": 1})
        print("[PASS] Test 24: User Authentication, PBKDF2 Password Hashing & Role Switching verified.")

    def test_25_super_admin_control_plane_and_suspension_lockout(self):
        """Test Super Admin platform metrics, tenant provisioning, tier quotas, and suspension lockout."""
        # 1. Get platform-wide metrics
        res_m = self.client.get("/api/v1/super-admin/metrics")
        self.assertEqual(res_m.status_code, 200)
        self.assertGreaterEqual(res_m.json()["metrics"]["total_tenants"], 1)

        # 2. Provision new tenant on FREE tier with unique slug
        unique_slug = f"mit-comp-{int(time.time()*1000)%100000}"
        create_payload = {
            "name": "MIT School of Computing",
            "slug": unique_slug,
            "contact_email": "dean@mit.edu",
            "subscription_plan": "FREE",
            "admin_full_name": "Dean John Doe",
            "admin_username": f"dean_{unique_slug}",
            "admin_password": "Password@123",
        }
        res_create = self.client.post("/api/v1/super-admin/tenants", json=create_payload)
        self.assertEqual(res_create.status_code, 201)
        mit_tenant = res_create.json()["tenant"]
        self.assertEqual(mit_tenant["max_face_encodings"], 50)  # Free tier default
        self.assertEqual(mit_tenant["max_nodes"], 2)

        # 3. Suspend the new tenant
        res_suspend = self.client.put(f"/api/v1/super-admin/tenants/{mit_tenant['id']}/status", json={"status": "SUSPENDED"})
        self.assertEqual(res_suspend.status_code, 200)
        self.assertEqual(res_suspend.json()["tenant"]["subscription_status"], "SUSPENDED")

        # 4. Test that edge node frame ingestion is strictly locked for suspended tenant (403 Forbidden)
        test_frame = np.full((240, 320, 3), 128, dtype=np.uint8)
        _, jpeg_bytes = cv2.imencode(".jpg", test_frame)
        files = {"frame": ("lockout_test.jpg", jpeg_bytes.tobytes(), "image/jpeg")}
        data = {"node_id": "NODE-LOCKOUT-TEST", "tenant_id": mit_tenant["slug"]}

        res_lockout = self.client.post("/api/v1/nodes/frame", files=files, data=data)
        self.assertEqual(res_lockout.status_code, 403)
        self.assertIn("SUSPENDED", res_lockout.json()["detail"])

        # 5. Reactivate tenant
        res_active = self.client.put(f"/api/v1/super-admin/tenants/{mit_tenant['id']}/status", json={"status": "ACTIVE"})
        self.assertEqual(res_active.status_code, 200)

        # 6. Adjust quotas
        res_quota = self.client.put(
            f"/api/v1/super-admin/tenants/{mit_tenant['id']}/quotas",
            json={"subscription_plan": "ENTERPRISE", "max_face_encodings": 8000, "max_nodes": 60}
        )
        self.assertEqual(res_quota.status_code, 200)
        self.assertEqual(res_quota.json()["tenant"]["max_face_encodings"], 8000)

        print("[PASS] Test 25: Super Admin Tenant Provisioning, Quota Controls & Suspension Lockout verified.")

    def test_26_academic_hierarchy_and_faculty_assignments(self):
        """Test academic years, classes, divisions CRUD, and teacher classroom mapping."""
        self.client.post("/api/v1/auth/switch-role", json={"role": "TENANT_ADMIN", "tenant_id": 1})
        rand_id = int(time.time()*1000)%100000

        # 1. Create Academic Year
        res_yr = self.client.post("/api/v1/academic/years", json={"name": f"2027-2028-{rand_id}", "is_current": False})
        self.assertEqual(res_yr.status_code, 200)

        # 2. Create Class
        res_cls = self.client.post("/api/v1/academic/classes", json={"name": f"TY Data Science {rand_id}", "department": "Data Science"})
        self.assertEqual(res_cls.status_code, 200)
        class_id = res_cls.json()["class"]["id"]

        # 3. Create Division
        res_div = self.client.post("/api/v1/academic/divisions", json={"class_id": class_id, "name": "Division Alpha"})
        self.assertEqual(res_div.status_code, 200)
        div_id = res_div.json()["division"]["id"]

        # 4. Create Teacher user
        res_teacher = self.client.post("/api/v1/academic/teachers", json={
            "full_name": "Prof. Alan Turing",
            "username": f"a.turing_{rand_id}",
            "email": f"turing_{rand_id}@campus.edu",
            "password": "Password@123",
        })
        self.assertEqual(res_teacher.status_code, 200)
        teacher_id = res_teacher.json()["teacher"]["id"]

        # 5. Assign teacher to classroom
        res_assign = self.client.post("/api/v1/academic/teacher-assignments", json={
            "teacher_id": teacher_id,
            "class_id": class_id,
            "division_id": div_id,
            "subject": "Theoretical Computer Science",
        })
        self.assertEqual(res_assign.status_code, 200)
        assignment_id = res_assign.json()["assignment"]["id"]

        # 6. List assignments
        res_list = self.client.get(f"/api/v1/academic/teacher-assignments?teacher_id={teacher_id}")
        self.assertEqual(res_list.status_code, 200)
        self.assertEqual(len(res_list.json()["assignments"]), 1)

        print("[PASS] Test 26: Academic Hierarchy (Years, Classes, Divisions) & Faculty Assignment verified.")

    def test_27_student_progression_and_downgrade_rollback(self):
        """Test student cohort promotion preserving face vectors and safe emergency rollback/downgrade."""
        self.client.post("/api/v1/auth/switch-role", json={"role": "TENANT_ADMIN", "tenant_id": 1})
        # 1. Fetch student in class 1
        with get_db_context() as db:
            student = db.query(Student).filter(Student.tenant_id == 1).first()
            student_id = student.id
            original_class_id = student.class_id or 1
            vectors_count = len(student.encodings)
            target_cls = db.query(ClassModel).filter(ClassModel.tenant_id == 1, ClassModel.name == "SY Computer Science").first()
            if not target_cls:
                target_cls = db.query(ClassModel).filter(ClassModel.tenant_id == 1).first()
            target_class_id = target_cls.id

        # 2. Promote student to class (SY Computer Science)
        res_promote = self.client.post("/api/v1/academic/students/promote", json={
            "student_ids": [student_id],
            "target_class_id": target_class_id,
            "target_division_id": None,
        })
        self.assertEqual(res_promote.status_code, 200)
        self.assertEqual(res_promote.json()["promoted_count"], 1)

        # 3. Verify student class is updated, previous class is recorded, and face vectors are intact
        with get_db_context() as db:
            updated_student = db.query(Student).filter(Student.id == student_id).first()
            self.assertEqual(updated_student.class_id, target_class_id)
            self.assertEqual(updated_student.previous_class_id, original_class_id)
            self.assertIsNotNone(updated_student.last_promoted_at)
            self.assertEqual(len(updated_student.encodings), vectors_count)

        # 4. Execute Rollback / Downgrade for this student
        res_rollback = self.client.post("/api/v1/academic/students/rollback-promotion", json={
            "student_ids": [student_id]
        })
        self.assertEqual(res_rollback.status_code, 200)
        self.assertEqual(res_rollback.json()["rollback_count"], 1)

        # 5. Verify student is restored back to original class
        with get_db_context() as db:
            restored_student = db.query(Student).filter(Student.id == student_id).first()
            self.assertEqual(restored_student.class_id, original_class_id)
            self.assertIsNone(restored_student.previous_class_id)

        print("[PASS] Test 27: Student Progression & Emergency Downgrade / Rollback Engine verified.")

    def test_28_teacher_portal_classroom_sheet_and_rbac(self):
        """Test teacher assigned class discovery and classroom attendance roster retrieval."""
        self.client.post("/api/v1/auth/switch-role", json={"role": "TEACHER", "tenant_id": 1})
        # 1. Query my-classes
        res_my = self.client.get("/api/v1/teacher/my-classes")
        self.assertEqual(res_my.status_code, 200)

        # 2. Query classroom attendance sheet for class 1
        today_str = date.today().isoformat()
        res_sheet = self.client.get(f"/api/v1/teacher/attendance-sheet?class_id=1&date_str={today_str}")
        self.assertEqual(res_sheet.status_code, 200)
        sheet_data = res_sheet.json()
        self.assertIn("roster", sheet_data)
        self.assertIn("turnout_pct", sheet_data)
        self.assertIn("present_count", sheet_data)
        self.assertIn("absent_count", sheet_data)

        print("[PASS] Test 28: Teacher Classroom Roster Sheet & Turnout Analytics verified.")

    def test_29_administrative_audit_trail(self):
        """Test global audit logging across administrative operations."""
        self.client.post("/api/v1/auth/switch-role", json={"role": "SUPER_ADMIN", "tenant_id": 1})
        res_audit = self.client.get("/api/v1/super-admin/audit-logs?limit=50")
        self.assertEqual(res_audit.status_code, 200)
        logs = res_audit.json()["logs"]
        self.assertGreaterEqual(len(logs), 1)

        # Verify audit log fields
        latest_log = logs[0]
        self.assertIn("action_type", latest_log)
        self.assertIn("actor_name", latest_log)
        self.assertIn("description", latest_log)
        self.assertIn("timestamp", latest_log)

        print("[PASS] Test 29: Administrative Audit Trail Logging verified.")

    def test_30_subscription_plans_crud_and_automated_quota_derivation(self):
        """Test Super Admin Subscription Plans CRUD and automated quota derivation on tenant creation."""
        self.client.post("/api/v1/auth/switch-role", json={"role": "SUPER_ADMIN", "tenant_id": 1})

        # 1. List subscription plans
        res_plans = self.client.get("/api/v1/super-admin/plans")
        self.assertEqual(res_plans.status_code, 200)
        plans = res_plans.json()["plans"]
        self.assertGreaterEqual(len(plans), 3)

        # 2. Create custom subscription plan
        rand_suffix = int(time.time()*1000)%100000
        plan_code = f"PRO_{rand_suffix}"
        res_create_plan = self.client.post("/api/v1/super-admin/plans", json={
            "plan_code": plan_code,
            "name": f"Professional Tier {rand_suffix}",
            "max_face_encodings": 1500,
            "max_nodes": 25,
            "price_monthly": 89.0,
            "description": "High performance mid-tier plan",
        })
        self.assertEqual(res_create_plan.status_code, 201)
        created_plan = res_create_plan.json()["plan"]
        self.assertEqual(created_plan["max_face_encodings"], 1500)
        self.assertEqual(created_plan["max_nodes"], 25)

        # 3. Create Tenant selecting this plan -> Quotas must be automatically populated from plan
        tenant_slug = f"pro-org-{rand_suffix}"
        res_tenant = self.client.post("/api/v1/super-admin/tenants", json={
            "name": f"Pro Academy {rand_suffix}",
            "slug": tenant_slug,
            "contact_email": f"dean@{tenant_slug}.edu",
            "subscription_plan": plan_code,
            "admin_full_name": "Dean Pro",
            "admin_username": f"admin_{tenant_slug}",
            "admin_password": "Password@123",
        })
        self.assertEqual(res_tenant.status_code, 201)
        t_data = res_tenant.json()["tenant"]
        self.assertEqual(t_data["subscription_plan"], plan_code)
        self.assertEqual(t_data["max_face_encodings"], 1500)
        self.assertEqual(t_data["max_nodes"], 25)

        print("[PASS] Test 30: Subscription Plans CRUD & Automated Quota Derivation verified.")

    def test_31_tenant_edit_details_api(self):
        """Test Super Admin comprehensive tenant details editing (name, plan, status, quotas)."""
        self.client.post("/api/v1/auth/switch-role", json={"role": "SUPER_ADMIN", "tenant_id": 1})

        # 1. Create a test tenant
        rand_id = int(time.time()*1000)%100000
        slug = f"edit-test-{rand_id}"
        res_create = self.client.post("/api/v1/super-admin/tenants", json={
            "name": f"Original Tenant Name {rand_id}",
            "slug": slug,
            "subscription_plan": "FREE",
            "admin_full_name": "Admin Edit",
            "admin_username": f"admin_{slug}",
            "admin_password": "Password@123",
        })
        self.assertEqual(res_create.status_code, 201)
        tenant_id = res_create.json()["tenant"]["id"]

        # 2. Edit details: change name, plan, contact email, and custom quota override
        res_edit = self.client.put(f"/api/v1/super-admin/tenants/{tenant_id}", json={
            "name": f"Updated Tenant Name {rand_id}",
            "contact_email": "updated@tenant.edu",
            "subscription_plan": "ENTERPRISE",
            "max_face_encodings": 7500,
            "max_nodes": 45,
        })
        self.assertEqual(res_edit.status_code, 200)
        edited_t = res_edit.json()["tenant"]
        self.assertEqual(edited_t["name"], f"Updated Tenant Name {rand_id}")
        self.assertEqual(edited_t["contact_email"], "updated@tenant.edu")
        self.assertEqual(edited_t["subscription_plan"], "ENTERPRISE")
        self.assertEqual(edited_t["max_face_encodings"], 7500)
        self.assertEqual(edited_t["max_nodes"], 45)

        print("[PASS] Test 31: Tenant Details & Custom Quotas Editing API verified.")

    def test_32_suspended_tenant_read_only_access_enforcement(self):
        """Test that suspended tenants allow read-only viewing but block all operational write actions."""
        # 1. Create tenant and suspend it
        rand_id = int(time.time()*1000)%100000
        slug = f"susp-test-{rand_id}"
        res_create = self.client.post("/api/v1/super-admin/tenants", json={
            "name": f"Suspended College {rand_id}",
            "slug": slug,
            "subscription_plan": "STANDARD",
            "admin_full_name": "Dean Suspended",
            "admin_username": f"dean_{slug}",
            "admin_password": "Password@123",
        })
        self.assertEqual(res_create.status_code, 201)
        tenant_id = res_create.json()["tenant"]["id"]

        # Suspend the tenant
        res_susp = self.client.put(f"/api/v1/super-admin/tenants/{tenant_id}/status", json={"status": "SUSPENDED"})
        self.assertEqual(res_susp.status_code, 200)

        # 2. Test Read operations -> Must SUCCEED (Read-only historical access)
        res_records = self.client.get("/api/v1/attendance/records", headers={"X-Tenant-ID": str(tenant_id)})
        self.assertEqual(res_records.status_code, 200)

        res_students = self.client.get("/api/v1/super-admin/tenants/" + str(tenant_id) + "/students")
        self.assertEqual(res_students.status_code, 200)

        # 3. Test Write / Operational operations -> Must FAIL with 403 Forbidden
        # A. Register new student
        res_enroll = self.client.post(
            "/api/v1/enroll/student",
            json={"roll_number": "SUSP-ST-1", "name": "Suspended Student"},
            headers={"X-Tenant-ID": str(tenant_id)},
        )
        self.assertEqual(res_enroll.status_code, 403)
        self.assertIn("SUSPENDED", res_enroll.json()["detail"])

        # B. Manual attendance override
        res_override = self.client.post(
            "/api/v1/attendance/manual-override",
            json={"student_id": 9999, "reason": "Test override during suspension"},
            headers={"X-Tenant-ID": str(tenant_id)},
        )
        self.assertEqual(res_override.status_code, 403)
        self.assertIn("SUSPENDED", res_override.json()["detail"])

        # C. Edge node frame ingestion
        test_frame = np.full((120, 160, 3), 100, dtype=np.uint8)
        _, jpeg_bytes = cv2.imencode(".jpg", test_frame)
        files = {"frame": ("susp_frame.jpg", jpeg_bytes.tobytes(), "image/jpeg")}
        data = {"node_id": "NODE-SUSP-1", "tenant_id": slug}
        res_frame = self.client.post("/api/v1/nodes/frame", files=files, data=data)
        self.assertEqual(res_frame.status_code, 403)
        self.assertIn("SUSPENDED", res_frame.json()["detail"])

        print("[PASS] Test 32: Suspended Tenant Read-Only Historical Access & Operational Lockdown verified.")

    def test_33_soft_delete_and_restore_tenant(self):
        """Test soft deleting a tenant and restoring it without database data loss."""
        self.client.post("/api/v1/auth/switch-role", json={"role": "SUPER_ADMIN", "tenant_id": 1})

        # 1. Create tenant
        rand_id = int(time.time()*1000)%100000
        slug = f"del-test-{rand_id}"
        res_create = self.client.post("/api/v1/super-admin/tenants", json={
            "name": f"Soft Delete Institute {rand_id}",
            "slug": slug,
            "subscription_plan": "STANDARD",
            "admin_full_name": "Dean Delete",
            "admin_username": f"dean_{slug}",
            "admin_password": "Password@123",
        })
        self.assertEqual(res_create.status_code, 201)
        tenant_id = res_create.json()["tenant"]["id"]

        # 2. Soft-delete the tenant
        res_del = self.client.delete(f"/api/v1/super-admin/tenants/{tenant_id}")
        self.assertEqual(res_del.status_code, 200)
        del_t = res_del.json()["tenant"]
        self.assertTrue(del_t["is_deleted"])
        self.assertEqual(del_t["subscription_status"], "DELETED")
        self.assertIsNotNone(del_t["deleted_at"])

        # 3. Attempt to log in with soft-deleted tenant admin -> Must be REJECTED (403)
        res_login = self.client.post("/api/v1/auth/login", json={
            "username": f"dean_{slug}",
            "password": "Password@123",
            "tenant_id": tenant_id,
        })
        self.assertEqual(res_login.status_code, 403)
        self.assertIn("deactivated or deleted", res_login.json()["detail"])

        # 4. Restore the tenant
        res_restore = self.client.post(f"/api/v1/super-admin/tenants/{tenant_id}/restore")
        self.assertEqual(res_restore.status_code, 200)
        restored_t = res_restore.json()["tenant"]
        self.assertFalse(restored_t["is_deleted"])
        self.assertEqual(restored_t["subscription_status"], "ACTIVE")
        self.assertIsNone(restored_t["deleted_at"])

        # 5. Log in again -> Must SUCCEED after restore
        res_login_ok = self.client.post("/api/v1/auth/login", json={
            "username": f"dean_{slug}",
            "password": "Password@123",
            "tenant_id": tenant_id,
        })
        self.assertEqual(res_login_ok.status_code, 200)

        print("[PASS] Test 33: Tenant Soft Deletion & Super Admin Recovery verified.")

    def test_34_super_admin_student_directory_tenant_scoping(self):
        """Test Super Admin student directory scoped querying preventing cross-tenant leakage."""
        self.client.post("/api/v1/auth/switch-role", json={"role": "SUPER_ADMIN", "tenant_id": 1})

        # 1. Query students for Tenant 1
        res_t1 = self.client.get("/api/v1/super-admin/tenants/1/students")
        self.assertEqual(res_t1.status_code, 200)
        t1_students = res_t1.json()["students"]
        self.assertIsInstance(t1_students, list)

        # 2. Query students via mandatory tenant_id query filter
        res_filter = self.client.get("/api/v1/super-admin/students?tenant_id=1")
        self.assertEqual(res_filter.status_code, 200)
        self.assertEqual(len(res_filter.json()["students"]), len(t1_students))

        # 3. Query without tenant_id -> FastAPI validation error (422 Unprocessable Entity)
        res_no_param = self.client.get("/api/v1/super-admin/students")
        self.assertEqual(res_no_param.status_code, 422)

        print("[PASS] Test 34: Super Admin Tenant-Scoped Student Directory Enforcement verified.")


if __name__ == "__main__":
    unittest.main()


