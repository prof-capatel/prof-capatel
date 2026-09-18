import unittest
import os
import sys
from datetime import date
from fastapi.testclient import TestClient

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.server.app import app
from src.database.session import SessionLocal
from src.database.models import (
    Tenant,
    User,
    Student,
    DesignationMaster,
    SalaryTemplate,
    EmployeeSalaryStructure,
    SalaryRevisionHistory,
    Department,
    CompanyLocation,
)
from src.server.rbac_middleware import create_access_token


class TestDesignationAndPayrollWorkflow(unittest.TestCase):
    """
    Comprehensive test suite verifying:
    1. Salary Template creation with customizable statutory compliance fields
    2. Linking Salary Template to Designation/Role Master
    3. Employee onboarding assigning Designation (auto-inheriting Designation template) with customizable overrides
    4. Employee onboarding with explicit custom Salary Template override
    5. Modifiable employee salary structure values with individual overrides
    6. Designation deletion protection with assigned employees
    7. Database hygiene and teardown
    """

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db = SessionLocal()

        # 1. Create or fetch dedicated test corporate tenant
        cls.tenant = cls.db.query(Tenant).filter(Tenant.slug == "test-desig-payroll-org").first()
        if not cls.tenant:
            cls.tenant = Tenant(
                name="Test Designation & Payroll Org",
                slug="test-desig-payroll-org",
                tenant_type="corporate",
                is_active=True,
            )
            cls.db.add(cls.tenant)
            cls.db.commit()
            cls.db.refresh(cls.tenant)

        # 2. Create test admin user
        cls.admin_user = cls.db.query(User).filter(User.username == "test_desig_admin").first()
        if not cls.admin_user:
            cls.admin_user = User(
                tenant_id=cls.tenant.id,
                username="test_desig_admin",
                email="admin@testdesigorg.com",
                full_name="Test Designation Admin User",
                role="TENANT_ADMIN",
                password_hash="test_hash_desig",
                is_active=True,
            )
            cls.db.add(cls.admin_user)
            cls.db.commit()
            cls.db.refresh(cls.admin_user)

        # 3. Create test department
        cls.dept = Department(
            tenant_id=cls.tenant.id,
            name="Engineering Division",
            code="ENG-DIV",
        )
        cls.db.add(cls.dept)
        cls.db.commit()
        cls.db.refresh(cls.dept)

        cls.token = create_access_token(
            user_id=cls.admin_user.id,
            role=cls.admin_user.role,
            tenant_id=cls.tenant.id,
            username=cls.admin_user.username,
        )
        cls.headers = {
            "Authorization": f"Bearer {cls.token}",
            "X-Tenant-ID": str(cls.tenant.id),
        }

    def setUp(self):
        self.refresh_session()

    def refresh_session(self):
        self.db.rollback()
        self.db.expire_all()

    @classmethod
    def tearDownClass(cls):
        """Purge all temporary test records."""
        try:
            cls.db.rollback()
            cls.db.query(SalaryRevisionHistory).filter(SalaryRevisionHistory.tenant_id == cls.tenant.id).delete()
            cls.db.query(EmployeeSalaryStructure).filter(EmployeeSalaryStructure.tenant_id == cls.tenant.id).delete()
            cls.db.query(Student).filter(Student.tenant_id == cls.tenant.id).delete()
            cls.db.query(DesignationMaster).filter(DesignationMaster.tenant_id == cls.tenant.id).delete()
            cls.db.query(SalaryTemplate).filter(SalaryTemplate.tenant_id == cls.tenant.id).delete()
            cls.db.query(CompanyLocation).filter(CompanyLocation.tenant_id == cls.tenant.id).delete()
            cls.db.query(Department).filter(Department.tenant_id == cls.tenant.id).delete()
            cls.db.query(User).filter(User.id == cls.admin_user.id).delete()
            cls.db.query(Tenant).filter(Tenant.id == cls.tenant.id).delete()
            cls.db.commit()
        except Exception as e:
            cls.db.rollback()
            print(f"Cleanup error in tearDownClass: {e}")
        finally:
            cls.db.close()

    def test_01_create_salary_template_with_statutory_options(self):
        """Test creating Salary Template with customizable statutory compliance rules."""
        res = self.client.post(
            "/api/v1/payroll/masters/templates",
            headers=self.headers,
            json={
                "name": "Staff Compensation Blueprint",
                "code": "STAFF-BLU",
                "compensation_model": "STRUCTURED_SALARY",
                "description": "Standard staff compensation package with EPF & ESIC enabled",
                "basic_percentage": 50.0,
                "hra_percentage": 20.0,
                "da_percentage": 5.0,
                "conveyance_fixed": 1600.0,
                "medical_fixed": 1250.0,
                "enable_pf": True,
                "pf_capped_at_ceiling": True,
                "enable_esi": True,
                "enable_pt": True,
                "is_active": True,
            },
        )
        self.assertIn(res.status_code, (200, 201), res.text)
        tpl_data = res.json()["data"]
        self.assertEqual(tpl_data["name"], "Staff Compensation Blueprint")
        self.assertTrue(tpl_data["enable_pf"])
        self.assertTrue(tpl_data["pf_capped_at_ceiling"])
        self.assertTrue(tpl_data["enable_esi"])
        self.assertTrue(tpl_data["enable_pt"])
        self.__class__.staff_template_id = tpl_data["id"]

        # Also create a Consultant template with PF and ESI disabled
        res_consultant = self.client.post(
            "/api/v1/payroll/masters/templates",
            headers=self.headers,
            json={
                "name": "Consultant Fixed Package",
                "code": "CONS-FIXED",
                "compensation_model": "MONTHLY_FIXED",
                "description": "Retainer contract with statutory deductions disabled",
                "basic_percentage": 100.0,
                "hra_percentage": 0.0,
                "da_percentage": 0.0,
                "conveyance_fixed": 0.0,
                "medical_fixed": 0.0,
                "enable_pf": False,
                "pf_capped_at_ceiling": False,
                "enable_esi": False,
                "enable_pt": False,
                "is_active": True,
            },
        )
        self.assertIn(res_consultant.status_code, (200, 201), res_consultant.text)
        consult_data = res_consultant.json()["data"]
        self.assertFalse(consult_data["enable_pf"])
        self.assertFalse(consult_data["enable_esi"])
        self.assertFalse(consult_data["enable_pt"])
        self.__class__.consultant_template_id = consult_data["id"]

    def test_02_assign_template_to_designation(self):
        """Test assigning Salary Template to Designation / Role Master."""
        # Create a Designation linked to staff_template_id
        res = self.client.post(
            "/api/v1/payroll/masters/designations",
            headers=self.headers,
            json={
                "title": "Software Engineer II",
                "code": "SWE-2",
                "salary_template_id": self.staff_template_id,
                "description": "Mid-level backend & full-stack engineer",
                "is_active": True,
            },
        )
        self.assertIn(res.status_code, (200, 201), res.text)
        data = res.json()["data"]
        self.assertEqual(data["salary_template_id"], self.staff_template_id)
        self.assertEqual(data["salary_template_name"], "Staff Compensation Blueprint")
        self.__class__.swe_designation_id = data["id"]

    def test_03_employee_onboarding_inherits_designation_template(self):
        """Test onboarding an employee with Designation, verifying auto-resolution of template and custom values."""
        res = self.client.post(
            "/api/v1/enroll/student",
            headers=self.headers,
            json={
                "roll_number": "EMP-DESIG-001",
                "name": "Ananya Roy",
                "department_id": self.dept.id,
                "department": self.dept.name,
                "user_role": "employee",
                "designation_id": self.swe_designation_id,
                "monthly_base_salary": 45000.0,
                "hourly_rate": 216.35,
            },
        )
        self.assertIn(res.status_code, (200, 201), res.text)
        emp_data = res.json()["student"]
        emp_id = emp_data["id"]
        self.__class__.emp_1_id = emp_id

        self.refresh_session()
        emp = self.db.query(Student).filter(Student.id == emp_id).first()
        self.assertIsNotNone(emp)
        self.assertEqual(emp.designation_id, self.swe_designation_id)
        self.assertEqual(emp.monthly_base_salary, 45000.0)

        # Check to_dict() resolution
        emp_dict = emp.to_dict()
        self.assertEqual(emp_dict["designation_id"], self.swe_designation_id)
        self.assertEqual(emp_dict["salary_template_id"], self.staff_template_id)

    def test_04_employee_onboarding_with_custom_template_override(self):
        """Test onboarding an employee with Designation but overriding with a specific custom template."""
        res = self.client.post(
            "/api/v1/enroll/student",
            headers=self.headers,
            json={
                "roll_number": "EMP-DESIG-002",
                "name": "Vikram Seth",
                "department_id": self.dept.id,
                "department": self.dept.name,
                "user_role": "employee",
                "designation_id": self.swe_designation_id,
                "salary_template_id": self.consultant_template_id,  # Overridden!
                "monthly_base_salary": 60000.0,
            },
        )
        self.assertIn(res.status_code, (200, 201), res.text)
        emp_data = res.json()["student"]
        emp_id = emp_data["id"]
        self.__class__.emp_2_id = emp_id

        self.refresh_session()
        emp = self.db.query(Student).filter(Student.id == emp_id).first()
        self.assertIsNotNone(emp)
        self.assertEqual(emp.designation_id, self.swe_designation_id)

        emp_dict = emp.to_dict()
        self.assertEqual(emp_dict["designation_id"], self.swe_designation_id)
        # Custom salary_template_id takes precedence over designation default
        self.assertEqual(emp_dict["salary_template_id"], self.consultant_template_id)

    def test_05_assign_individual_structure_with_modifiable_overrides(self):
        """Test assigning individual salary structure with custom overrides (custom basic, HRA, allowances)."""
        res = self.client.post(
            "/api/v1/payroll/structure/assign",
            headers=self.headers,
            json={
                "student_id": self.emp_1_id,
                "template_id": self.staff_template_id,
                "compensation_model": "STRUCTURED_SALARY",
                "annual_ctc": 600000.0,
                "monthly_gross": 50000.0,
                "monthly_basic": 25000.0,
                "monthly_hra": 10000.0,
                "conveyance_allowance": 2000.0,   # Custom override!
                "medical_allowance": 1500.0,      # Custom override!
                "special_allowance": 11500.0,
                "effective_from_date": date.today().isoformat(),
                "revision_reason": "Annual Merit Increment",
            },
        )
        self.assertIn(res.status_code, (200, 201), res.text)
        st_data = res.json()["data"]
        self.assertEqual(st_data["monthly_gross"], 50000.0)
        self.assertEqual(st_data["monthly_basic"], 25000.0)
        self.assertEqual(st_data["conveyance_allowance"], 2000.0)
        self.assertEqual(st_data["medical_allowance"], 1500.0)

        # Verify revision history
        rev_res = self.client.get(f"/api/v1/payroll/employee/{self.emp_1_id}/structure", headers=self.headers)
        self.assertEqual(rev_res.status_code, 200)
        history = rev_res.json()["revision_history"]
        self.assertGreaterEqual(len(history), 1)
        self.assertEqual(history[0]["revision_reason"], "Annual Merit Increment")

    def test_06_employee_update_profile_updates_designation(self):
        """Test updating employee profile designation via PUT /api/v1/enroll/student/{id}."""
        # Create a new Tech Lead designation
        res_lead = self.client.post(
            "/api/v1/payroll/masters/designations",
            headers=self.headers,
            json={
                "title": "Lead Software Engineer",
                "code": "LEAD-SWE",
                "salary_template_id": self.staff_template_id,
                "description": "Technical Lead and squad mentor",
                "is_active": True,
            },
        )
        self.assertIn(res_lead.status_code, (200, 201), res_lead.text)
        new_desig_id = res_lead.json()["data"]["id"]

        # Update emp_1 to new designation
        update_res = self.client.put(
            f"/api/v1/enroll/student/{self.emp_1_id}",
            headers=self.headers,
            json={
                "name": "Ananya Roy (Promoted)",
                "roll_number": "EMP-DESIG-001",
                "designation_id": new_desig_id,
                "designation": "Lead Software Engineer",
                "monthly_base_salary": 75000.0,
            },
        )
        self.assertEqual(update_res.status_code, 200, update_res.text)

        self.refresh_session()
        emp = self.db.query(Student).filter(Student.id == self.emp_1_id).first()
        self.assertEqual(emp.designation_id, new_desig_id)
        self.assertEqual(emp.name, "Ananya Roy (Promoted)")
        self.assertEqual(emp.to_dict()["designation_id"], new_desig_id)

    def test_07_designation_deletion_protection(self):
        """Test that Designation cannot be deleted while assigned to an active employee, but can be after unassigning."""
        # emp_2 is assigned to swe_designation_id
        del_res = self.client.delete(f"/api/v1/payroll/masters/designations/{self.swe_designation_id}", headers=self.headers)
        self.assertEqual(del_res.status_code, 400, "Should block deletion of designation with assigned employees")
        self.assertIn("employee(s) are currently assigned", del_res.json()["detail"])

        # Reassign emp_2 designation_id to None
        update_emp2 = self.client.put(
            f"/api/v1/enroll/student/{self.emp_2_id}",
            headers=self.headers,
            json={
                "name": "Vikram Seth",
                "roll_number": "EMP-DESIG-002",
                "designation_id": None,
                "designation": None,
            },
        )
        self.assertEqual(update_emp2.status_code, 200)

        # Now delete swe_designation_id
        del_res2 = self.client.delete(f"/api/v1/payroll/masters/designations/{self.swe_designation_id}", headers=self.headers)
        self.assertEqual(del_res2.status_code, 200, "Should delete successfully after employee is unassigned")


if __name__ == "__main__":
    unittest.main()
