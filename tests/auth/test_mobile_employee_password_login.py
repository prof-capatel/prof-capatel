import unittest
from fastapi.testclient import TestClient
from src.server.app import app
from src.database.session import SessionLocal
from src.database.models import Tenant, Student, User
from src.utils.auth_utils import hash_password


class TestMobileEmployeePasswordLogin(unittest.TestCase):
    """Test suite validating mobile app username and password login for industry tenants."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db = SessionLocal()

        # Find or use corporate tenant pulin1 (id 106)
        cls.tenant = cls.db.query(Tenant).filter(Tenant.slug == "pulin1").first()
        if not cls.tenant:
            cls.tenant = cls.db.query(Tenant).filter(Tenant.tenant_type == "corporate").first()

        # Ensure employee profile exists in this tenant
        cls.student = cls.db.query(Student).filter(
            Student.tenant_id == cls.tenant.id,
            Student.is_active == True,
        ).first()

        # Ensure linked user exists with known password
        candidate_username = cls.student.roll_number.strip().lower()
        cls.user = cls.db.query(User).filter(
            User.username == candidate_username,
            User.tenant_id == cls.tenant.id,
        ).first()

        cls.test_password = "TestEmpPassword@2026"
        hashed = hash_password(cls.test_password)

        if not cls.user:
            cls.user = User(
                tenant_id=cls.tenant.id,
                username=candidate_username,
                email=f"{candidate_username}@tenant{cls.tenant.id}.test",
                password_hash=hashed,
                role="EMPLOYEE",
                full_name=cls.student.name,
                is_active=True,
            )
            cls.db.add(cls.user)
            cls.db.flush()
        else:
            cls.user.password_hash = hashed
            cls.user.is_active = True

        cls.student.user_id = cls.user.id
        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_employee_password_login_success(self):
        """Test employee can log in via /api/v1/auth/login using exact username and password."""
        res = self.client.post(
            "/api/v1/auth/login",
            json={
                "username": self.user.username,
                "password": self.test_password,
                "tenant_identifier": self.tenant.slug,
            },
        )
        self.assertEqual(res.status_code, 200, f"Expected 200 OK, got: {res.text}")
        data = res.json()
        self.assertEqual(data.get("status"), "success")
        self.assertIn("access_token", data)
        self.assertIsNotNone(data.get("user"))
        self.assertEqual(data["user"]["id"], self.user.id)
        self.assertEqual(data["user"]["student_id"], self.student.id)

    def test_02_employee_login_with_uppercase_roll_number(self):
        """Test employee can log in using their Employee ID / Roll Number even in uppercase."""
        res = self.client.post(
            "/api/v1/auth/login",
            json={
                "username": self.student.roll_number.upper(),
                "password": self.test_password,
                "tenant_identifier": self.tenant.slug,
            },
        )
        self.assertEqual(res.status_code, 200, f"Expected 200 OK, got: {res.text}")
        data = res.json()
        self.assertEqual(data.get("status"), "success")
        self.assertEqual(data["user"]["student_id"], self.student.id)

    def test_03_token_usable_on_employee_self_service(self):
        """Test that the token issued by /api/v1/auth/login authenticates employee endpoints."""
        login_res = self.client.post(
            "/api/v1/auth/login",
            json={
                "username": self.user.username,
                "password": self.test_password,
                "tenant_identifier": self.tenant.slug,
            },
        )
        token = login_res.json()["access_token"]

        # Call /api/v1/employee/me
        me_res = self.client.get(
            "/api/v1/employee/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(me_res.status_code, 200, f"Failed on /me: {me_res.text}")
        self.assertEqual(me_res.json().get("employee", {}).get("id"), self.student.id)

        # Call /api/v1/employee/attendance
        att_res = self.client.get(
            "/api/v1/employee/attendance",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(att_res.status_code, 200, f"Failed on /attendance: {att_res.text}")

    def test_04_invalid_password_returns_401(self):
        """Test that incorrect credentials return 401 Unauthorized without 500 server error."""
        res = self.client.post(
            "/api/v1/auth/login",
            json={
                "username": self.user.username,
                "password": "CompletelyWrongPassword123!",
                "tenant_identifier": self.tenant.slug,
            },
        )
        self.assertEqual(res.status_code, 401)
        data = res.json()
        self.assertIn("Invalid", data.get("detail", ""))


if __name__ == "__main__":
    unittest.main()
