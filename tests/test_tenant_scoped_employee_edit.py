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
        """Test that corporate tenant employee directory renders corporate roles in edit modal without school roles."""
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

        # 2. Check editUserRole contains corporate options and excludes student/teacher
        self.assertIn('id="editUserRole"', html)
        self.assertIn('value="employee"', html)
        self.assertIn('value="manager"', html)
        self.assertIn('value="admin_staff"', html)
        self.assertIn('value="contractor"', html)
        self.assertIn('value="intern"', html)

        # Extract editUserRole block
        start_idx = html.find('id="editUserRole"')
        end_idx = html.find('</select>', start_idx)
        role_select_html = html[start_idx:end_idx]

        self.assertNotIn('value="student"', role_select_html, "Corporate tenant editUserRole must not contain 'student'")
        self.assertNotIn('value="teacher"', role_select_html, "Corporate tenant editUserRole must not contain 'teacher'")

    def test_corporate_registration_page_labels_and_roles(self):
        """Test that /enroll route renders 'Register New Employee' and corporate-specific labels for corporate tenant."""
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

        # Verify userRole select block in enroll.html
        start_idx = html.find('id="userRole"')
        end_idx = html.find('</select>', start_idx)
        user_role_html = html[start_idx:end_idx]

        self.assertIn('value="employee"', user_role_html)
        self.assertIn('value="manager"', user_role_html)
        self.assertNotIn('value="student"', user_role_html)
        self.assertNotIn('value="teacher"', user_role_html)

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

if __name__ == "__main__":
    unittest.main()
