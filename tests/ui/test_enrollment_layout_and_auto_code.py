"""
Unit & Integration Tests for Register New Employee Form Layout & Biometric Capture Refinement.
Validates:
1. Auto-generated employee codes on load with inline refresh button.
2. 3-Angle Face Capture controls relocated underneath the live camera feed window.
3. Mode action buttons (Live Webcam Guided & Batch 3-Photo Upload) placed above camera/dropzone window.
4. Tightened whitespace & streamlined self-enrollment link banner.
5. Corporate vs Educational tenant terminology and form fields preservation.
"""
import sys
import os
from pathlib import Path
import unittest
from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.database.session import get_db, init_db
from src.database.models import Tenant, User
from src.server.app import app
from src.server.rbac_middleware import create_access_token


class TestEnrollmentLayoutAndAutoCode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)
        cls.db = next(get_db())

    def _get_auth_client(self, tenant_slug: str):
        tenant = self.db.query(Tenant).filter(Tenant.slug == tenant_slug).first()
        self.assertIsNotNone(tenant, f"Tenant {tenant_slug} must exist")
        admin_u = self.db.query(User).filter(User.tenant_id == tenant.id, User.role == "TENANT_ADMIN", User.is_active == True).first()
        self.assertIsNotNone(admin_u, f"Admin for {tenant_slug} must exist")

        token = create_access_token(
            user_id=admin_u.id, role="TENANT_ADMIN", tenant_id=admin_u.tenant_id, username=admin_u.username
        )
        client = TestClient(app)
        client.cookies.set("access_token", token)
        return client, tenant

    def test_01_auto_code_input_and_script_present(self):
        """Verify auto-code generation fields, inline refresh buttons, and JS functions exist."""
        client, tenant = self._get_auth_client("the-retail-store")
        res = client.get("/enroll")
        self.assertEqual(res.status_code, 200)
        html = res.text

        # Monospace input and inline refresh button
        self.assertIn("auto-code-group", html)
        self.assertIn("auto-code-refresh-btn", html)
        self.assertIn('id="rollNumber"', html)
        self.assertIn('id="batchRollNumber"', html)
        self.assertIn("regenerateEmployeeCode('webcam')", html)
        self.assertIn("regenerateEmployeeCode('batch')", html)

        # JS functions
        self.assertIn("function generateRandomEmployeeCode()", html)
        self.assertIn("function regenerateEmployeeCode(mode)", html)
        self.assertIn("DOMContentLoaded", html)
        self.assertIn("rollInput.value = generateRandomEmployeeCode()", html)

    def test_02_camera_controls_relocated_underneath_camera_feed(self):
        """Verify 3-angle face capture buttons are nested under live webcam preview in right card."""
        client, tenant = self._get_auth_client("the-retail-store")
        res = client.get("/enroll")
        self.assertEqual(res.status_code, 200)
        html = res.text

        # Elements inside capture hub card
        self.assertIn('id="enrollCaptureHubCard"', html)
        self.assertIn('id="webcamVideo"', html)
        self.assertIn('id="captureCanvas"', html)
        self.assertIn('id="enrollProgressSection"', html)
        self.assertIn('id="btnCapFrontal"', html)
        self.assertIn('id="btnCapLeft"', html)
        self.assertIn('id="btnCapRight"', html)

        # Ensure DOM order: video comes before the 3-angle buttons
        pos_video = html.find('id="webcamVideo"')
        pos_progress = html.find('id="enrollProgressSection"')
        pos_frontal = html.find('id="btnCapFrontal"')
        pos_left = html.find('id="btnCapLeft"')
        pos_right = html.find('id="btnCapRight"')

        self.assertNotEqual(pos_video, -1)
        self.assertNotEqual(pos_progress, -1)
        self.assertTrue(pos_video < pos_progress < pos_frontal < pos_left < pos_right,
                        "3-angle capture buttons must be ordered underneath the webcam video feed")

    def test_03_mode_tabs_positioned_above_camera_and_dropzone(self):
        """Verify mode switcher action buttons are placed in card-header above camera and dropzone."""
        client, tenant = self._get_auth_client("the-retail-store")
        res = client.get("/enroll")
        self.assertEqual(res.status_code, 200)
        html = res.text

        # Tab button IDs and actions
        self.assertIn('id="tabBtnWebcam"', html)
        self.assertIn('id="tabBtnBatch"', html)
        self.assertIn("switchEnrollMode('webcam')", html)
        self.assertIn("switchEnrollMode('batch')", html)

        # Ensure tab buttons appear before the camera preview in the right card
        pos_tab_webcam = html.find('id="tabBtnWebcam"')
        pos_video = html.find('id="webcamVideo"')
        self.assertTrue(pos_tab_webcam < pos_video, "Mode switcher buttons must be above the camera window")

    def test_04_corporate_tenant_labels_and_fields(self):
        """Verify corporate tenant displays appropriate corporate terminology and fields."""
        client, tenant = self._get_auth_client("the-retail-store")
        res = client.get("/enroll")
        self.assertEqual(res.status_code, 200)
        html = res.text

        self.assertIn("Employee Self-Enrollment Portal", html)
        self.assertIn("Employee / Staff Information", html)
        self.assertIn("Register Employee & Start Face Capture", html)
        self.assertIn("Live Employee Face Capture", html)
        self.assertIn("Date of Joining (DOJ)", html)
        self.assertIn("Branch / Office Location", html)
        self.assertIn("Salary Structure", html)
        self.assertIn("Work shift", html)
        self.assertIn("Designation", html)

    def test_05_educational_tenant_labels_and_fields(self):
        """Verify educational tenant displays educational terminology and fields."""
        edu_tenant = self.db.query(Tenant).filter(Tenant.tenant_type == "educational", Tenant.is_active == True).first()
        self.assertIsNotNone(edu_tenant, "Must have at least one active educational tenant")

        edu_admin = self.db.query(User).filter(User.tenant_id == edu_tenant.id, User.role == "TENANT_ADMIN", User.is_active == True).first()
        if not edu_admin:
            edu_admin = self.db.query(User).filter(User.role == "SUPER_ADMIN", User.is_active == True).first()

        token = create_access_token(
            user_id=edu_admin.id, role=edu_admin.role, tenant_id=edu_tenant.id, username=edu_admin.username
        )
        client = TestClient(app)
        client.cookies.set("access_token", token)

        res = client.get("/enroll")
        self.assertEqual(res.status_code, 200)
        html = res.text

        self.assertIn("Student Self-Registration Portal", html)
        self.assertIn("Student / Member Information", html)
        self.assertIn("Register Profile & Start Face Capture", html)
        self.assertIn("Live Enrollment View", html)
        self.assertIn("Class / Semester", html)


if __name__ == "__main__":
    unittest.main()
