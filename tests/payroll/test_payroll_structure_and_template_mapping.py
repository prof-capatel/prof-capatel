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


class TestPayrollStructureAndTemplateMapping(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db = SessionLocal()

        # 1. Create or fetch dedicated test corporate tenant
        cls.tenant = cls.db.query(Tenant).filter(Tenant.slug == "test-corp-payroll-struct").first()
        if not cls.tenant:
            cls.tenant = Tenant(
                name="Test Corp Payroll Struct Org",
                slug="test-corp-payroll-struct",
                tenant_type="corporate",
                subscription_plan="PRO",
                is_active=True,
            )
            cls.db.add(cls.tenant)
            cls.db.commit()
            cls.db.refresh(cls.tenant)
        else:
            cls.tenant.subscription_plan = "PRO"
            cls.db.commit()

        # 2. Create test admin user
        cls.admin_user = cls.db.query(User).filter(User.username == "test_corp_admin_struct").first()
        if not cls.admin_user:
            cls.admin_user = User(
                tenant_id=cls.tenant.id,
                username="test_corp_admin_struct",
                email="admin@testcorpstruct.com",
                full_name="Test Corp Struct Admin",
                role="TENANT_ADMIN",
                password_hash="test_hash",
                is_active=True,
            )
            cls.db.add(cls.admin_user)
            cls.db.commit()
            cls.db.refresh(cls.admin_user)

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

    def test_01_create_salary_template_and_link_to_designation(self):
        """Test creating salary template and mapping it to a designation master."""
        # 1. Create Salary Template
        tpl_payload = {
            "name": "Senior Engineering CTC Blueprint",
            "code": "ENG-SR-CTC",
            "compensation_model": "STRUCTURED_SALARY",
            "description": "Standard 50/20/10 CTC Template for Sr Developers",
            "basic_percentage": 50.0,
            "hra_percentage": 20.0,
            "da_percentage": 10.0,
            "conveyance_fixed": 1600.0,
            "medical_fixed": 1250.0,
            "enable_pf": True,
            "pf_capped_at_ceiling": True,
            "enable_esi": False,
            "enable_pt": True,
            "is_active": True,
        }
        res_tpl = self.client.post(
            "/api/v1/payroll/masters/templates",
            headers=self.headers,
            json=tpl_payload,
        )
        self.assertEqual(res_tpl.status_code, 200, f"Template create failed: {res_tpl.text}")
        tpl_data = res_tpl.json()["data"]
        tpl_id = tpl_data["id"]
        self.assertEqual(tpl_data["code"], "ENG-SR-CTC")

        # 2. Create Designation with mapped salary_template_id
        desig_payload = {
            "title": "Principal Architect",
            "code": "PRIN-ARCH",
            "salary_template_id": tpl_id,
            "description": "Technical Strategy & Architecture Lead",
            "is_active": True,
        }
        res_desig = self.client.post(
            "/api/v1/payroll/masters/designations",
            headers=self.headers,
            json=desig_payload,
        )
        self.assertEqual(res_desig.status_code, 200, f"Designation create failed: {res_desig.text}")
        desig_data = res_desig.json()["data"]
        desig_id = desig_data["id"]
        self.assertEqual(desig_data["salary_template_id"], tpl_id)
        self.assertEqual(desig_data["salary_template_name"], "Senior Engineering CTC Blueprint")
        self.assertEqual(desig_data["salary_template_code"], "ENG-SR-CTC")

        # 3. Verify Designation List endpoint contains template metadata
        res_list = self.client.get(
            "/api/v1/payroll/masters/designations",
            headers=self.headers,
        )
        self.assertEqual(res_list.status_code, 200)
        desigs = res_list.json()["data"]
        matching = next((d for d in desigs if d["id"] == desig_id), None)
        self.assertIsNotNone(matching)
        self.assertEqual(matching["salary_template_id"], tpl_id)
        self.assertEqual(matching["salary_template_name"], "Senior Engineering CTC Blueprint")

        # 4. Update Designation to clear or change template
        res_update = self.client.put(
            f"/api/v1/payroll/masters/designations/{desig_id}",
            headers=self.headers,
            json={"salary_template_id": None},
        )
        self.assertEqual(res_update.status_code, 200)
        self.assertIsNone(res_update.json()["data"]["salary_template_id"])

        # Re-link template for subsequent employee tests
        res_relink = self.client.put(
            f"/api/v1/payroll/masters/designations/{desig_id}",
            headers=self.headers,
            json={"salary_template_id": tpl_id},
        )
        self.assertEqual(res_relink.status_code, 200)
        self.assertEqual(res_relink.json()["data"]["salary_template_id"], tpl_id)

    def test_02_employee_onboarding_with_designation_default_template(self):
        """Test employee registration inherits designation default template and creates active salary structure."""
        self.refresh_session()
        desig = self.db.query(DesignationMaster).filter(
            DesignationMaster.tenant_id == self.tenant.id,
            DesignationMaster.code == "PRIN-ARCH",
        ).first()
        self.assertIsNotNone(desig)

        # Register employee with designation_id (no explicit salary_template_id provided)
        emp_payload = {
            "roll_number": "EMP-ARCH-001",
            "name": "Devendra Mukherjee",
            "user_role": "employee",
            "designation_id": desig.id,
            "monthly_base_salary": 100000.0,
            "date_of_joining": "2026-03-01",
        }
        res_reg = self.client.post(
            "/api/v1/enroll/student",
            headers=self.headers,
            json=emp_payload,
        )
        self.assertEqual(res_reg.status_code, 200, f"Register employee failed: {res_reg.text}")
        emp_data = res_reg.json()["student"]
        emp_id = emp_data["id"]

        # Verify EmployeeSalaryStructure was automatically generated
        self.refresh_session()
        struct = self.db.query(EmployeeSalaryStructure).filter(
            EmployeeSalaryStructure.tenant_id == self.tenant.id,
            EmployeeSalaryStructure.student_id == emp_id,
            EmployeeSalaryStructure.is_current == True,
        ).first()
        self.assertIsNotNone(struct, "Expected EmployeeSalaryStructure to be auto-created")
        self.assertEqual(struct.template_id, desig.salary_template_id)
        self.assertEqual(struct.compensation_model, "STRUCTURED_SALARY")
        self.assertEqual(struct.monthly_gross, 100000.0)
        self.assertEqual(struct.annual_ctc, 1200000.0)

        # Basic 50% = 50000, DA 10% = 10000, HRA 20% of Basic = 10000, Conv = 1600, Med = 1250, Special = balance
        self.assertEqual(struct.monthly_basic, 50000.0)
        self.assertEqual(struct.monthly_da, 10000.0)
        self.assertEqual(struct.monthly_hra, 10000.0)
        self.assertEqual(struct.conveyance_allowance, 1600.0)
        self.assertEqual(struct.medical_allowance, 1250.0)
        expected_special = 100000.0 - (50000.0 + 10000.0 + 10000.0 + 1600.0 + 1250.0)
        self.assertEqual(struct.special_allowance, expected_special)
        self.assertTrue(struct.enable_pf)
        self.assertFalse(struct.enable_esi)
        self.assertTrue(struct.enable_pt)
        self.assertEqual(struct.effective_from_date, date(2026, 3, 1))

    def test_03_employee_onboarding_with_explicit_template_override(self):
        """Test employee registration with explicit salary_template_id overrides designation template."""
        # Create a second template: Fixed Stipend
        res_stipend = self.client.post(
            "/api/v1/payroll/masters/templates",
            headers=self.headers,
            json={
                "name": "Graduate Trainee Stipend",
                "code": "STIPEND-25K",
                "compensation_model": "STIPEND",
                "basic_percentage": 100.0,
                "hra_percentage": 0.0,
                "da_percentage": 0.0,
                "conveyance_fixed": 0.0,
                "medical_fixed": 0.0,
                "enable_pf": False,
                "enable_esi": False,
                "enable_pt": False,
                "is_active": True,
            },
        )
        self.assertEqual(res_stipend.status_code, 200)
        stipend_tpl_id = res_stipend.json()["data"]["id"]

        self.refresh_session()
        desig = self.db.query(DesignationMaster).filter(
            DesignationMaster.tenant_id == self.tenant.id,
            DesignationMaster.code == "PRIN-ARCH",
        ).first()

        # Register employee specifying stipend_tpl_id explicitly
        emp_payload = {
            "roll_number": "EMP-INT-002",
            "name": "Siddharth Verma",
            "user_role": "employee",
            "designation_id": desig.id,
            "salary_template_id": stipend_tpl_id,
            "monthly_base_salary": 25000.0,
            "date_of_joining": "2026-04-01",
        }
        res_reg = self.client.post(
            "/api/v1/enroll/student",
            headers=self.headers,
            json=emp_payload,
        )
        self.assertEqual(res_reg.status_code, 200)
        emp_id = res_reg.json()["student"]["id"]

        self.refresh_session()
        struct = self.db.query(EmployeeSalaryStructure).filter(
            EmployeeSalaryStructure.tenant_id == self.tenant.id,
            EmployeeSalaryStructure.student_id == emp_id,
            EmployeeSalaryStructure.is_current == True,
        ).first()
        self.assertIsNotNone(struct)
        self.assertEqual(struct.template_id, stipend_tpl_id)
        self.assertEqual(struct.compensation_model, "STIPEND")
        self.assertEqual(struct.monthly_gross, 25000.0)
        self.assertEqual(struct.fixed_stipend, 25000.0)
        self.assertFalse(struct.enable_pf)

    def test_04_assign_salary_structure_and_revision_history(self):
        """Test /api/v1/payroll/structure/assign creates revision history and transitions previous structure."""
        self.refresh_session()
        emp = self.db.query(Student).filter(
            Student.tenant_id == self.tenant.id,
            Student.roll_number == "EMP-ARCH-001",
        ).first()
        self.assertIsNotNone(emp)

        old_struct = self.db.query(EmployeeSalaryStructure).filter(
            EmployeeSalaryStructure.tenant_id == self.tenant.id,
            EmployeeSalaryStructure.student_id == emp.id,
            EmployeeSalaryStructure.is_current == True,
        ).first()
        self.assertIsNotNone(old_struct)

        # Assign revised structure effective from 2026-07-01 (Promotion / CTC hike to 1,50,000/mo)
        assign_payload = {
            "student_id": emp.id,
            "compensation_model": "STRUCTURED_SALARY",
            "annual_ctc": 1800000.0,
            "monthly_gross": 150000.0,
            "monthly_basic": 75000.0,
            "monthly_hra": 15000.0,
            "monthly_da": 15000.0,
            "conveyance_allowance": 2000.0,
            "medical_allowance": 1500.0,
            "special_allowance": 41500.0,
            "enable_pf": True,
            "enable_esi": False,
            "enable_pt": True,
            "effective_from_date": "2026-07-01",
            "revision_reason": "Annual Performance Appraisal & Merit Hike",
        }
        res_assign = self.client.post(
            "/api/v1/payroll/structure/assign",
            headers=self.headers,
            json=assign_payload,
        )
        self.assertEqual(res_assign.status_code, 200, f"Assign structure failed: {res_assign.text}")

        # Refresh database records
        self.refresh_session()
        old_struct_refreshed = self.db.query(EmployeeSalaryStructure).filter(
            EmployeeSalaryStructure.id == old_struct.id
        ).first()
        self.assertFalse(old_struct_refreshed.is_current)
        self.assertEqual(old_struct_refreshed.effective_to_date, date(2026, 6, 30))

        new_struct = self.db.query(EmployeeSalaryStructure).filter(
            EmployeeSalaryStructure.tenant_id == self.tenant.id,
            EmployeeSalaryStructure.student_id == emp.id,
            EmployeeSalaryStructure.is_current == True,
        ).first()
        self.assertIsNotNone(new_struct)
        self.assertEqual(new_struct.monthly_gross, 150000.0)
        self.assertEqual(new_struct.annual_ctc, 1800000.0)
        self.assertEqual(new_struct.effective_from_date, date(2026, 7, 1))

        # Check revision history
        revisions = self.db.query(SalaryRevisionHistory).filter(
            SalaryRevisionHistory.tenant_id == self.tenant.id,
            SalaryRevisionHistory.student_id == emp.id,
        ).all()
        self.assertEqual(len(revisions), 1)
        self.assertEqual(revisions[0].previous_monthly_gross, 100000.0)
        self.assertEqual(revisions[0].new_monthly_gross, 150000.0)
        self.assertEqual(revisions[0].revision_reason, "Annual Performance Appraisal & Merit Hike")

    def test_05_update_employee_profile_updates_salary_structure(self):
        """Test PUT /api/v1/enroll/student/{id} updates employee template and generates new current structure."""
        self.refresh_session()
        emp = self.db.query(Student).filter(
            Student.tenant_id == self.tenant.id,
            Student.roll_number == "EMP-INT-002",
        ).first()
        self.assertIsNotNone(emp)

        eng_tpl = self.db.query(SalaryTemplate).filter(
            SalaryTemplate.tenant_id == self.tenant.id,
            SalaryTemplate.code == "ENG-SR-CTC",
        ).first()
        self.assertIsNotNone(eng_tpl)

        # Update employee to Full-time Engineer with monthly salary 60,000 and template
        update_payload = {
            "roll_number": emp.roll_number,
            "name": emp.name,
            "user_role": "employee",
            "monthly_base_salary": 60000.0,
            "salary_template_id": eng_tpl.id,
        }
        res_update = self.client.put(
            f"/api/v1/enroll/student/{emp.id}",
            headers=self.headers,
            json=update_payload,
        )
        self.assertEqual(res_update.status_code, 200, f"Update profile failed: {res_update.text}")

        self.refresh_session()
        updated_struct = self.db.query(EmployeeSalaryStructure).filter(
            EmployeeSalaryStructure.tenant_id == self.tenant.id,
            EmployeeSalaryStructure.student_id == emp.id,
            EmployeeSalaryStructure.is_current == True,
        ).first()
        self.assertIsNotNone(updated_struct)
        self.assertEqual(updated_struct.template_id, eng_tpl.id)
        self.assertEqual(updated_struct.compensation_model, "STRUCTURED_SALARY")
        self.assertEqual(updated_struct.monthly_gross, 60000.0)
        self.assertEqual(updated_struct.monthly_basic, 30000.0)  # 50% of 60k
        self.assertEqual(updated_struct.monthly_da, 6000.0)    # 10% of 60k
        self.assertEqual(updated_struct.monthly_hra, 6000.0)   # 20% of Basic (30k)

    def test_06_structure_endpoints_and_route_aliases(self):
        """Test /api/v1/payroll/structures and /api/v1/payroll/employees aliases return 200 OK and valid structure overview."""
        self.refresh_session()
        emp = self.db.query(Student).filter(
            Student.tenant_id == self.tenant.id,
            Student.roll_number == "EMP-ARCH-001",
        ).first()
        self.assertIsNotNone(emp)

        # 1. Test GET /api/v1/payroll/structures
        res_structs = self.client.get("/api/v1/payroll/structures", headers=self.headers)
        self.assertEqual(res_structs.status_code, 200)
        data_structs = res_structs.json()
        self.assertEqual(data_structs["status"], "success")
        self.assertIsInstance(data_structs["data"], list)
        self.assertGreater(len(data_structs["data"]), 0)

        # Verify employee item schema
        emp_item = next((item for item in data_structs["data"] if item["id"] == emp.id), None)
        self.assertIsNotNone(emp_item)
        self.assertIn("active_structure", emp_item)
        self.assertIn("default_template_id", emp_item)
        self.assertEqual(emp_item["roll_number"], "EMP-ARCH-001")

        # 2. Test GET /api/v1/payroll/employees alias
        res_employees = self.client.get("/api/v1/payroll/employees", headers=self.headers)
        self.assertEqual(res_employees.status_code, 200)
        data_employees = res_employees.json()
        self.assertEqual(data_employees["status"], "success")
        self.assertEqual(len(data_employees["data"]), len(data_structs["data"]))

        # 3. Test GET /api/v1/payroll/employee/{id}/structure
        res_single = self.client.get(f"/api/v1/payroll/employee/{emp.id}/structure", headers=self.headers)
        self.assertEqual(res_single.status_code, 200)
        data_single = res_single.json()
        self.assertEqual(data_single["status"], "success")
        self.assertEqual(data_single["employee"]["id"], emp.id)
        self.assertIsNotNone(data_single["current_structure"])
        self.assertIsInstance(data_single["revision_history"], list)

        # 4. Test GET /api/v1/payroll/employees/{id}/structure alias
        res_alias1 = self.client.get(f"/api/v1/payroll/employees/{emp.id}/structure", headers=self.headers)
        self.assertEqual(res_alias1.status_code, 200)

        # 5. Test GET /api/v1/payroll/structures/{id} alias
        res_alias2 = self.client.get(f"/api/v1/payroll/structures/{emp.id}", headers=self.headers)
        self.assertEqual(res_alias2.status_code, 200)


if __name__ == "__main__":
    unittest.main()
