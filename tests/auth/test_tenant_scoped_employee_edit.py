import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from fastapi.testclient import TestClient
from src.server.app import app
from src.database.session import get_db
from src.database.models import Tenant, Student, User
from src.server.rbac_middleware import create_access_token

class TestTenantScopedEmployeeEdit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db = next(get_db())

    def test_corporate_tenant_edit_modal_roles_and_labels(self):
        """Test that corporate tenant employee directory renders corporate edit modal with hidden userRole and designation selector."""
        corp_tenant = self.db.query(Tenant).filter(
            Tenant.tenant_type.in_(["corporate", "company", "enterprise"]),
            Tenant.is_active == True,
            Tenant.is_deleted == False
        ).first()
        self.assertIsNotNone(corp_tenant, "Must have at least one active corporate tenant")

        corp_admin = self.db.query(User).filter(User.tenant_id == corp_tenant.id, User.role == "TENANT_ADMIN").first()
        if not corp_admin:
            corp_admin = User(
                username=f"admin_test_{corp_tenant.slug}",
                role="TENANT_ADMIN",
                tenant_id=corp_tenant.id,
                is_active=True
            )
            self.db.add(corp_admin)
            self.db.commit()
            self.db.refresh(corp_admin)

        token = create_access_token(
            user_id=corp_admin.id, role="TENANT_ADMIN", tenant_id=corp_tenant.id, username=corp_admin.username
        )
        self.client.cookies.set("access_token", token)

        res = self.client.get("/employees")
        self.assertEqual(res.status_code, 200)
        html = res.text

        # 1. Edit modal exists and has corporate title
        self.assertIn('id="editStudentModal"', html)
        self.assertIn("Edit Employee Profile", html)

        # 2. Check editUserRole is hidden for corporate tenant to prevent redundancy
        self.assertIn('<input type="hidden" id="editUserRole" value="employee">', html)

        # 3. Check designation and salary structure fields are present
        self.assertIn('id="editDesignationSelect"', html)
        self.assertIn('id="editSalaryTemplateSelect"', html)

    def test_corporate_registration_page_labels_and_roles(self):
        """Test that /enroll route renders 'Register New Employee' and hidden userRole for corporate tenant."""
        corp_tenant = self.db.query(Tenant).filter(
            Tenant.tenant_type.in_(["corporate", "company", "enterprise"]),
            Tenant.is_active == True,
            Tenant.is_deleted == False
        ).first()
        self.assertIsNotNone(corp_tenant)

        corp_admin = self.db.query(User).filter(User.tenant_id == corp_tenant.id, User.role == "TENANT_ADMIN").first()
        token = create_access_token(
            user_id=corp_admin.id, role="TENANT_ADMIN", tenant_id=corp_tenant.id, username=corp_admin.username
        )
        self.client.cookies.set("access_token", token)

        res = self.client.get("/enroll")
        self.assertEqual(res.status_code, 200)
        html = res.text

        # Verify page title and header
        self.assertIn("Register New Employee", html)
        self.assertNotIn("<h2>Enroll New Student</h2>", html)
        self.assertIn("1. Employee / Staff Information", html)
        self.assertIn("Live Employee Face Capture", html)
        self.assertIn("Register Employee & Start Face Capture", html)
        self.assertIn("Employee Details & Batch Upload", html)

        # Verify hidden userRole input for corporate deduplication
        self.assertIn('<input type="hidden" id="userRole" value="employee">', html)
        self.assertIn('<input type="hidden" id="batchUserRole" value="employee">', html)
        self.assertIn('id="enrollDesignationSelect"', html)

    def test_educational_tenant_edit_modal_and_enroll(self):
        """Test that educational tenant edit modal and enroll page retain student/teacher options."""
        edu_tenant = self.db.query(Tenant).filter(
            Tenant.tenant_type == "educational",
            Tenant.is_active == True,
            Tenant.is_deleted == False
        ).first()
        self.assertIsNotNone(edu_tenant)

        edu_admin = self.db.query(User).filter(User.tenant_id == edu_tenant.id, User.role == "TENANT_ADMIN").first()
        if not edu_admin:
            edu_admin = self.db.query(User).filter(User.role == "SUPER_ADMIN").first()

        token = create_access_token(
            user_id=edu_admin.id, role=edu_admin.role, tenant_id=edu_tenant.id, username=edu_admin.username
        )
        self.client.cookies.set("access_token", token)

        # 1. Directory Edit Modal
        res = self.client.get("/students")
        self.assertEqual(res.status_code, 200)
        html = res.text

        start_idx = html.find('id="editUserRole"')
        end_idx = html.find('</select>', start_idx)
        role_select_html = html[start_idx:end_idx]

        self.assertIn('value="student"', role_select_html)
        self.assertIn('value="teacher"', role_select_html)

        # 2. Enroll Page
        res_enroll = self.client.get("/enroll")
        self.assertEqual(res_enroll.status_code, 200)
        html_enroll = res_enroll.text
        self.assertIn("Enroll New Student", html_enroll)
        self.assertIn("1. Student / Member Information", html_enroll)

    def test_get_student_profile_endpoint(self):
        """Test GET /api/v1/enroll/student/{id} returns profile dict and photo previews."""
        corp_tenant = self.db.query(Tenant).filter(
            Tenant.tenant_type.in_(["corporate", "company", "enterprise"]),
            Tenant.is_active == True,
            Tenant.is_deleted == False
        ).first()
        self.assertIsNotNone(corp_tenant)

        corp_admin = self.db.query(User).filter(User.tenant_id == corp_tenant.id, User.role == "TENANT_ADMIN").first()
        token = create_access_token(
            user_id=corp_admin.id, role="TENANT_ADMIN", tenant_id=corp_tenant.id, username=corp_admin.username
        )
        self.client.cookies.set("access_token", token)

        student = self.db.query(Student).filter(Student.tenant_id == corp_tenant.id).first()
        if student:
            res = self.client.get(f"/api/v1/enroll/student/{student.id}")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["status"], "success")
            self.assertIn("student", data)
            self.assertEqual(data["student"]["id"], student.id)
            self.assertIn("photos", data["student"])

    def test_image_quality_evaluation_tolerance(self):
        """Test evaluate_image_quality allows normal webcam frames and rejects severe blur/darkness."""
        import numpy as np
        import cv2
        from src.core.camera_utils import evaluate_image_quality

        # 1. Clear frame with moderate texture (simulating normal webcam face frame)
        img = np.zeros((480, 640, 3), dtype=np.uint8) + 128
        # Add high-contrast facial features / edges
        cv2.rectangle(img, (200, 150), (440, 380), (80, 80, 80), -1)
        cv2.circle(img, (260, 220), 25, (220, 220, 220), -1)
        cv2.circle(img, (380, 220), 25, (220, 220, 220), -1)
        cv2.line(img, (320, 240), (320, 300), (20, 20, 20), 4)
        cv2.ellipse(img, (320, 340), (45, 20), 0, 0, 180, (20, 20, 20), 4)

        is_good, msg = evaluate_image_quality(img)
        self.assertTrue(is_good, f"Should accept standard sharp webcam frame: {msg}")

        # 2. Heavily blurred frame (Laplacian variance < 10)
        blurred = cv2.GaussianBlur(img, (51, 51), 0)
        is_blurred, blur_msg = evaluate_image_quality(blurred)
        self.assertFalse(is_blurred, "Should reject severely out-of-focus frame")
        self.assertIn("blurry", blur_msg.lower())

        # 3. Completely dark frame
        dark = np.zeros((480, 640, 3), dtype=np.uint8) + 10
        is_dark, dark_msg = evaluate_image_quality(dark)
        self.assertFalse(is_dark, "Should reject dark frame")
        self.assertIn("dark", dark_msg.lower())


if __name__ == "__main__":
    unittest.main()

