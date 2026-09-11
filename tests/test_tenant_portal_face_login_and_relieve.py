"""
Unit & Integration Tests for Tenant Portal Biometric Face-Authentication Login,
Employee Relieve/Reinstate Workflow, and Role-Based Access Routing.
"""
import os
import sys
import base64
from datetime import datetime
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
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
from src.database.models import (
    Tenant,
    User,
    Student,
    FaceEncoding,
    AuditLog,
    AttendanceRecord,
)
from src.utils.auth_utils import hash_password
from src.server.app import app
from src.server.routes.api_employee_portal import decode_employee_token
from src.server.rbac_middleware import decode_access_token


class TestTenantPortalFaceLoginAndRelieve(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.client = TestClient(app)
        self.clean_test_data()

    def tearDown(self):
        self.clean_test_data()

    def clean_test_data(self):
        with get_db_context() as db:
            test_rolls = ["EMP_FLOGIN_01", "ADMIN_FLOGIN_01", "EMP_RELIEVE_TEST"]
            st_ids = [s.id for s in db.query(Student).filter(Student.roll_number.in_(test_rolls)).all()]
            if st_ids:
                db.query(FaceEncoding).filter(FaceEncoding.student_id.in_(st_ids)).delete(synchronize_session=False)
                db.query(AttendanceRecord).filter(AttendanceRecord.student_id.in_(st_ids)).delete(synchronize_session=False)
                db.query(AuditLog).filter(AuditLog.target_id.in_([str(i) for i in st_ids])).delete(synchronize_session=False)
                db.query(Student).filter(Student.id.in_(st_ids)).delete(synchronize_session=False)
                db.commit()

            # Clean test user if created
            test_usernames = ["ADMIN_FLOGIN_01"]
            db.query(User).filter(User.username.in_(test_usernames)).delete(synchronize_session=False)
            db.commit()

    @patch("src.server.routes.api_auth.FaceEngine.compute_single_face_vector")
    @patch("src.server.routes.api_auth.decode_image_bytes")
    def test_01_tenant_portal_face_login_as_employee(self, mock_decode, mock_compute_vector):
        """Test seamless face-login for an employee on a corporate tenant portal."""
        # Setup mock dummy face frame and vector
        mock_decode.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        dummy_vec = np.zeros(128, dtype=np.float32)
        dummy_vec[0] = 1.0
        mock_compute_vector.return_value = (dummy_vec, (10, 10, 50, 50), "Face detected")

        with get_db_context() as db:
            ssec = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            self.assertIsNotNone(ssec, "SSEC tenant must exist")
            ssec_id = ssec.id

            emp = Student(
                tenant_id=ssec.id,
                roll_number="EMP_FLOGIN_01",
                name="Alice Employee",
                user_role="employee",
                department="Engineering",
                cadre_level="Staff",
                is_active=True,
                employment_status="ACTIVE",
            )
            db.add(emp)
            db.flush()

            # Attach face encoding matching dummy_vec
            enc = FaceEncoding.from_numpy(
                student_id=emp.id,
                vector=dummy_vec,
                tenant_id=ssec.id,
            )
            db.add(enc)
            db.commit()

        # Perform face login request
        payload = {
            "tenant_identifier": "ssec",
            "photo_base64": "data:image/jpeg;base64," + base64.b64encode(b"fake_jpeg_data").decode("utf-8"),
        }

        res = self.client.post("/api/v1/auth/tenant/face-login", json=payload)
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["role"], "EMPLOYEE")
        self.assertEqual(data["user_name"], "Alice Employee")
        self.assertIn("/employee/ssec/dashboard", data["redirect_url"])

        # Check cookies issued
        cookies = res.cookies
        self.assertIn("access_token", cookies)
        self.assertIn("emp_session_token", cookies)
        self.assertEqual(cookies.get("active_role"), "EMPLOYEE")
        self.assertEqual(cookies.get("active_tenant_id"), str(ssec_id))

        # Validate employee token claims
        claims = decode_employee_token(cookies["emp_session_token"])
        self.assertEqual(claims["roll_number"], "EMP_FLOGIN_01")
        self.assertEqual(claims["tenant_id"], ssec_id)

    @patch("src.server.routes.api_auth.FaceEngine.compute_single_face_vector")
    @patch("src.server.routes.api_auth.decode_image_bytes")
    def test_02_tenant_portal_face_login_as_admin(self, mock_decode, mock_compute_vector):
        """Test face-login for an administrator auto-routes to admin dashboard."""
        mock_decode.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        dummy_vec = np.zeros(128, dtype=np.float32)
        dummy_vec[1] = 1.0
        mock_compute_vector.return_value = (dummy_vec, (10, 10, 50, 50), "Face detected")

        with get_db_context() as db:
            ssec = db.query(Tenant).filter(Tenant.slug == "ssec").first()

            admin_user = User(
                tenant_id=ssec.id,
                username="ADMIN_FLOGIN_01",
                full_name="Sarah Manager",
                email="sarah@ssec.com",
                role="TENANT_ADMIN",
                password_hash=hash_password("Admin@123"),
                is_active=True,
            )
            db.add(admin_user)
            db.flush()

            admin_st = Student(
                tenant_id=ssec.id,
                user_id=admin_user.id,
                roll_number="ADMIN_FLOGIN_01",
                name="Sarah Manager",
                user_role="admin",
                department="Management",
                cadre_level="Executive",
                is_active=True,
                employment_status="ACTIVE",
            )
            db.add(admin_st)
            db.flush()

            enc = FaceEncoding.from_numpy(
                student_id=admin_st.id,
                vector=dummy_vec,
                tenant_id=ssec.id,
            )
            db.add(enc)
            db.commit()

        payload = {
            "tenant_identifier": "ssec",
            "photo_base64": "data:image/jpeg;base64," + base64.b64encode(b"fake_jpeg_data").decode("utf-8"),
        }

        res = self.client.post("/api/v1/auth/tenant/face-login", json=payload)
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["role"], "TENANT_ADMIN")
        self.assertEqual(data["redirect_url"], "/")

        cookies = res.cookies
        self.assertIn("access_token", cookies)
        self.assertEqual(cookies.get("active_role"), "TENANT_ADMIN")

    @patch("src.server.routes.api_auth.FaceEngine.compute_single_face_vector")
    @patch("src.server.routes.api_auth.decode_image_bytes")
    def test_03_tenant_portal_face_login_relieved_employee_rejected(self, mock_decode, mock_compute_vector):
        """Test relieved/inactive employee face login is rejected with 403 Forbidden or 404."""
        mock_decode.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        dummy_vec = np.zeros(128, dtype=np.float32)
        dummy_vec[2] = 1.0
        mock_compute_vector.return_value = (dummy_vec, (10, 10, 50, 50), "Face detected")

        with get_db_context() as db:
            ssec = db.query(Tenant).filter(Tenant.slug == "ssec").first()

            emp = Student(
                tenant_id=ssec.id,
                roll_number="EMP_FLOGIN_01",
                name="Relieved Worker",
                user_role="employee",
                department="Engineering",
                is_active=False,
                employment_status="RELIEVED",
            )
            db.add(emp)
            db.flush()

            enc = FaceEncoding.from_numpy(
                student_id=emp.id,
                vector=dummy_vec,
                tenant_id=ssec.id,
            )
            db.add(enc)
            db.commit()

        payload = {
            "tenant_identifier": "ssec",
            "photo_base64": "data:image/jpeg;base64," + base64.b64encode(b"fake_jpeg_data").decode("utf-8"),
        }

        res = self.client.post("/api/v1/auth/tenant/face-login", json=payload)
        self.assertIn(res.status_code, [403, 404])

    @patch("src.server.routes.api_auth.FaceEngine.compute_single_face_vector")
    @patch("src.server.routes.api_auth.decode_image_bytes")
    def test_04_tenant_portal_face_login_unmatched_face(self, mock_decode, mock_compute_vector):
        """Test unmatched face returns 401 Unauthorized."""
        mock_decode.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        probe_vec = np.ones(128, dtype=np.float32) * 5.0
        mock_compute_vector.return_value = (probe_vec, (10, 10, 50, 50), "Face detected")

        with get_db_context() as db:
            ssec = db.query(Tenant).filter(Tenant.slug == "ssec").first()

            emp = Student(
                tenant_id=ssec.id,
                roll_number="EMP_FLOGIN_01",
                name="Active Person",
                user_role="employee",
                is_active=True,
                employment_status="ACTIVE",
            )
            db.add(emp)
            db.flush()

            enrolled_vec = np.zeros(128, dtype=np.float32)
            enc = FaceEncoding.from_numpy(
                student_id=emp.id,
                vector=enrolled_vec,
                tenant_id=ssec.id,
            )
            db.add(enc)
            db.commit()

        payload = {
            "tenant_identifier": "ssec",
            "photo_base64": "data:image/jpeg;base64," + base64.b64encode(b"fake_jpeg_data").decode("utf-8"),
        }

        res = self.client.post("/api/v1/auth/tenant/face-login", json=payload)
        self.assertEqual(res.status_code, 401)
        self.assertIn("Face not recognized", res.json()["detail"])

    def test_05_relieve_and_reinstate_employee_lifecycle(self):
        """Test the full employee relieving & reinstatement API and status lifecycle."""
        with get_db_context() as db:
            ssec = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            ssec_id = str(ssec.id)
            tenant_int_id = ssec.id

            emp = Student(
                tenant_id=ssec.id,
                roll_number="EMP_RELIEVE_TEST",
                name="Bob Test",
                user_role="employee",
                department="Operations",
                is_active=True,
                employment_status="ACTIVE",
            )
            db.add(emp)
            db.commit()
            db.refresh(emp)
            emp_id = emp.id

        # 1. Relieve Employee
        relieve_payload = {
            "employment_status": "RELIEVED",
            "reason": "Resigned for higher studies",
            "relieved_at": "2026-09-30",
        }
        res = self.client.post(
            f"/api/v1/enroll/student/{emp_id}/relieve",
            json=relieve_payload,
            headers={"X-Tenant-ID": ssec_id},
        )
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertEqual(data["status"], "success")

        with get_db_context() as db:
            updated_emp = db.query(Student).filter(Student.id == emp_id).first()
            self.assertFalse(updated_emp.is_active)
            self.assertEqual(updated_emp.employment_status, "RELIEVED")
            self.assertIn("Resigned", updated_emp.relieving_reason)

            # Check audit log created
            audit = db.query(AuditLog).filter(
                AuditLog.tenant_id == tenant_int_id,
                AuditLog.action_type == "EMPLOYEE_RELIEVED",
                AuditLog.target_id == str(emp_id),
            ).first()
            self.assertIsNotNone(audit)

        # 2. Reinstate Employee
        reinstate_payload = {"reason": "Rehired under new contract"}
        res2 = self.client.post(
            f"/api/v1/enroll/student/{emp_id}/reinstate",
            json=reinstate_payload,
            headers={"X-Tenant-ID": ssec_id},
        )
        self.assertEqual(res2.status_code, 200, res2.text)

        with get_db_context() as db:
            reinstated_emp = db.query(Student).filter(Student.id == emp_id).first()
            self.assertTrue(reinstated_emp.is_active)
            self.assertEqual(reinstated_emp.employment_status, "ACTIVE")
            self.assertIsNone(reinstated_emp.relieved_at)
            self.assertIsNone(reinstated_emp.relieving_reason)

    def test_06_corporate_portal_view_rendering(self):
        """Test corporate portal renders biometric face scanner and shutter audio scripts."""
        res = self.client.get("/portal/ssec")
        self.assertEqual(res.status_code, 200)
        html = res.text
        self.assertIn("camera-viewport", html)
        self.assertIn("playShutterAndChime", html)
        self.assertIn("Scan Face to Sign In", html)
        self.assertIn("Switch to Password Sign In", html)

    def test_07_educational_portal_view_rendering(self):
        """Test educational portal renders standard credential/role login without disruption."""
        res = self.client.get("/portal/default")
        self.assertEqual(res.status_code, 200)
        html = res.text
        self.assertIn("loginUsername", html)
        self.assertIn("loginPassword", html)
        self.assertIn("Select Role", html)


if __name__ == "__main__":
    unittest.main()
