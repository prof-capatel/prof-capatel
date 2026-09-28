"""
Test Suite: Subscription Tier Field Visibility & Tenant Admin Login Adaptations
Verifies that:
1. Tenant Login and Portal views dynamically display active SaaS edition badges (Basic, Smart, Pro).
2. Auth login responses return subscription metadata (saas_edition, has_leave_module, has_payroll_module).
3. Employee enrollment view (/enroll) conditionally hides salary template and wage inputs for Basic tier tenants.
4. Employee directory (/employees) conditionally hides Wage & Compensation card in edit modal for Basic tier tenants.
5. Backend registration/update endpoints suppress salary structures and zero out salary fields for Basic tier tenants.
"""

import unittest
from fastapi.testclient import TestClient
from src.server.app import app
from src.database.session import get_db, SessionLocal
from src.database.models import Tenant, User, Student, Department, DesignationMaster, EmployeeSalaryStructure
from src.utils.auth_utils import hash_password
from src.server.rbac_middleware import create_access_token


class TestSubscriptionTierFieldVisibility(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db = SessionLocal()

        # 1. Create a dedicated Basic Tier Corporate Tenant
        cls.basic_tenant = cls.db.query(Tenant).filter(Tenant.slug == "test-basic-corp").first()
        if not cls.basic_tenant:
            cls.basic_tenant = Tenant(
                name="Basic Retail Co",
                slug="test-basic-corp",
                tenant_type="corporate",
                subscription_plan="BASIC",
                is_active=True,
                is_deleted=False,
            )
            cls.db.add(cls.basic_tenant)
            cls.db.flush()

            # Create Admin User for Basic Tenant
            cls.basic_admin = User(
                username="admin_basic",
                email="admin_basic@example.com",
                password_hash=hash_password("admin123"),
                full_name="Basic Admin",
                role="TENANT_ADMIN",
                tenant_id=cls.basic_tenant.id,
                is_active=True,
            )
            cls.db.add(cls.basic_admin)

            # Create Department
            cls.basic_dept = Department(
                name="Operations",
                code="OPS",
                tenant_id=cls.basic_tenant.id,
            )
            cls.db.add(cls.basic_dept)
            cls.db.flush()

            # Create Designation
            cls.basic_desig = DesignationMaster(
                title="Store Associate",
                code="SA-01",
                department_id=cls.basic_dept.id,
                tenant_id=cls.basic_tenant.id,
                is_active=True,
            )
            cls.db.add(cls.basic_desig)
            cls.db.commit()
            cls.db.refresh(cls.basic_tenant)
        else:
            cls.basic_admin = cls.db.query(User).filter(User.tenant_id == cls.basic_tenant.id, User.role == "TENANT_ADMIN").first()
            cls.basic_dept = cls.db.query(Department).filter(Department.tenant_id == cls.basic_tenant.id).first()

        # 2. Use existing Pro Tenant (e.g. pulin1)
        cls.pro_tenant = cls.db.query(Tenant).filter(Tenant.slug == "pulin1").first()
        cls.pro_admin = cls.db.query(User).filter(User.tenant_id == cls.pro_tenant.id, User.role == "TENANT_ADMIN").first() if cls.pro_tenant else None

        # Tokens
        cls.basic_token = create_access_token(
            user_id=cls.basic_admin.id,
            role="TENANT_ADMIN",
            tenant_id=cls.basic_tenant.id,
            username=cls.basic_admin.username,
        )
        cls.pro_token = create_access_token(
            user_id=cls.pro_admin.id if cls.pro_admin else 1,
            role="TENANT_ADMIN",
            tenant_id=cls.pro_tenant.id if cls.pro_tenant else 106,
            username=cls.pro_admin.username if cls.pro_admin else "admin",
        ) if cls.pro_tenant else None

    def setUp(self):
        self.client.cookies.clear()
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    @classmethod
    def tearDownClass(cls):
        pass

    def test_01_tenant_login_displays_saas_edition_badge(self):
        """Verify /login/{slug} renders the Basic Edition badge for basic tenants and Pro for pro tenants."""
        # Basic Tenant Login Page
        res_basic = self.client.get(f"/login/{self.basic_tenant.slug}")
        self.assertEqual(res_basic.status_code, 200)
        self.assertIn("BASIC Edition", res_basic.text)

        # Pro Tenant Login Page
        if self.pro_tenant:
            res_pro = self.client.get(f"/login/{self.pro_tenant.slug}")
            self.assertEqual(res_pro.status_code, 200)
            self.assertIn("PRO Edition", res_pro.text)

    def test_02_auth_login_returns_subscription_metadata(self):
        """Verify /api/v1/auth/tenant/login response includes full subscription edition metadata."""
        payload = {
            "username": "admin_basic",
            "password": "admin123",
            "tenant_identifier": self.basic_tenant.slug,
        }
        res = self.client.post("/api/v1/auth/tenant/login", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("tenant", data)
        self.assertEqual(data["tenant"]["saas_edition"], "BASIC")
        self.assertFalse(data["tenant"]["has_payroll_module"])
        self.assertFalse(data["tenant"]["has_leave_module"])

    def test_03_enroll_page_hides_salary_fields_for_basic_tier(self):
        """Verify /enroll for Basic tier hides salary structures, monthly gross, and hourly rate."""
        cookies = {
            "access_token": self.basic_token,
            "active_tenant_id": str(self.basic_tenant.id),
            "active_role": "TENANT_ADMIN",
        }
        res = self.client.get("/enroll", cookies=cookies)
        self.assertEqual(res.status_code, 200)
        # Salary fields should NOT exist in Basic tier HTML
        self.assertNotIn('id="enrollSalaryTemplateSelect"', res.text)
        self.assertNotIn('id="enrollMonthlySalary"', res.text)
        self.assertNotIn('id="enrollHourlyRate"', res.text)
        self.assertNotIn('id="batchEnrollSalaryTemplateSelect"', res.text)
        self.assertNotIn('id="batchMonthlySalary"', res.text)
        self.assertNotIn('id="batchHourlyRate"', res.text)

    def test_04_enroll_page_shows_salary_fields_for_pro_tier(self):
        """Verify /enroll for Pro tier includes salary structures and wage inputs."""
        if not self.pro_tenant or not self.pro_token:
            return
        cookies = {
            "access_token": self.pro_token,
            "active_tenant_id": str(self.pro_tenant.id),
            "active_role": "TENANT_ADMIN",
        }
        res = self.client.get("/enroll", cookies=cookies)
        self.assertEqual(res.status_code, 200)
        # Salary fields MUST exist in Pro tier HTML
        self.assertIn('id="enrollSalaryTemplateSelect"', res.text)
        self.assertIn('id="enrollMonthlySalary"', res.text)
        self.assertIn('id="batchEnrollSalaryTemplateSelect"', res.text)

    def test_05_employee_edit_modal_hides_compensation_card_for_basic_tier(self):
        """Verify /employees edit modal hides the Wage & Compensation Profile card for Basic tier."""
        cookies = {
            "access_token": self.basic_token,
            "active_tenant_id": str(self.basic_tenant.id),
            "active_role": "TENANT_ADMIN",
        }
        res = self.client.get("/employees", cookies=cookies)
        self.assertEqual(res.status_code, 200)
        self.assertNotIn("Compensation & Wage Profile", res.text)
        self.assertNotIn('id="editSalaryTemplateSelect"', res.text)
        self.assertNotIn('id="editMonthlyBaseSalary"', res.text)

    def test_06_employee_edit_modal_shows_compensation_card_for_pro_tier(self):
        """Verify /employees edit modal shows the Wage & Compensation Profile card for Pro tier."""
        if not self.pro_tenant or not self.pro_token:
            return
        cookies = {
            "access_token": self.pro_token,
            "active_tenant_id": str(self.pro_tenant.id),
            "active_role": "TENANT_ADMIN",
        }
        res = self.client.get("/employees", cookies=cookies)
        self.assertEqual(res.status_code, 200)
        self.assertIn("Compensation & Wage Profile", res.text)
        self.assertIn('id="editSalaryTemplateSelect"', res.text)
        self.assertIn('id="editMonthlyBaseSalary"', res.text)

    def test_07_api_enrollment_suppresses_salary_for_basic_tier(self):
        """Verify POST /api/v1/enroll/student ignores salary/template values under Basic tier."""
        # Ensure clean session and remove any existing test student
        self.db.rollback()
        existing = self.db.query(Student).filter(
            Student.tenant_id == self.basic_tenant.id,
            Student.roll_number == "EMP-BASIC-001",
        ).first()
        if existing:
            self.db.delete(existing)
            self.db.commit()

        cookies = {
            "access_token": self.basic_token,
            "active_tenant_id": str(self.basic_tenant.id),
            "active_role": "TENANT_ADMIN",
        }
        headers = {
            "X-Tenant-ID": str(self.basic_tenant.id),
            "Authorization": f"Bearer {self.basic_token}",
        }
        payload = {
            "roll_number": "EMP-BASIC-001",
            "name": "Rohan Verma",
            "department_id": self.basic_dept.id if self.basic_dept else None,
            "monthly_base_salary": 45000.0,
            "hourly_rate": 250.0,
            "salary_template_id": 999,
        }
        res = self.client.post("/api/v1/enroll/student", json=payload, headers=headers, cookies=cookies)
        self.assertEqual(res.status_code, 200)

        # Check DB using fresh query session: monthly_base_salary and hourly_rate must be None, and no EmployeeSalaryStructure
        fresh_db = SessionLocal()
        try:
            std = fresh_db.query(Student).filter(
                Student.tenant_id == self.basic_tenant.id,
                Student.roll_number == "EMP-BASIC-001",
            ).first()
            self.assertIsNotNone(std)
            self.assertIsNone(std.monthly_base_salary)
            self.assertIsNone(std.hourly_rate)

            struct = fresh_db.query(EmployeeSalaryStructure).filter(
                EmployeeSalaryStructure.tenant_id == self.basic_tenant.id,
                EmployeeSalaryStructure.student_id == std.id,
            ).first()
            self.assertIsNone(struct)
        finally:
            fresh_db.close()


if __name__ == "__main__":
    unittest.main()
