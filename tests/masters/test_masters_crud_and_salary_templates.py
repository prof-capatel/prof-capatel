import unittest
import os
import sys
from fastapi.testclient import TestClient

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.server.app import app
from src.database.session import get_db, SessionLocal
from src.database.models import (
    Tenant,
    User,
    Student,
    CompanyLocation,
    DesignationMaster,
    SalaryTemplate,
    EmployeeSalaryStructure,
    Department,
)
from src.server.rbac_middleware import create_access_token


class TestMastersCrudAndSalaryTemplates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db = SessionLocal()

        # Create or fetch corporate test tenant
        cls.tenant = cls.db.query(Tenant).filter(Tenant.slug == "test-corp-masters").first()
        if not cls.tenant:
            cls.tenant = Tenant(
                name="Test Corp Masters Org",
                slug="test-corp-masters",
                tenant_type="corporate",
                is_active=True,
            )
            cls.db.add(cls.tenant)
            cls.db.commit()
            cls.db.refresh(cls.tenant)

        # Create test admin user
        cls.admin_user = cls.db.query(User).filter(User.username == "test_corp_admin_masters").first()
        if not cls.admin_user:
            cls.admin_user = User(
                tenant_id=cls.tenant.id,
                username="test_corp_admin_masters",
                email="admin@testcorpmasters.com",
                full_name="Test Corp Admin",
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

    @classmethod
    def tearDownClass(cls):
        # Purge test records
        try:
            cls.db.query(EmployeeSalaryStructure).filter(EmployeeSalaryStructure.tenant_id == cls.tenant.id).delete()
            cls.db.query(Student).filter(Student.tenant_id == cls.tenant.id).delete()
            cls.db.query(SalaryTemplate).filter(SalaryTemplate.tenant_id == cls.tenant.id).delete()
            cls.db.query(DesignationMaster).filter(DesignationMaster.tenant_id == cls.tenant.id).delete()
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

    def test_01_locations_crud_and_delete_protection(self):
        """Test Company Locations full CRUD and employee assignment delete protection (1 A)."""
        # 1. Create Location
        res = self.client.post(
            "/api/v1/payroll/masters/locations",
            headers=self.headers,
            json={
                "name": "Pune Innovation Hub",
                "code": "PN-HUB",
                "city": "Pune",
                "state": "Maharashtra",
                "address": "Magarpatta Cybercity, Tower 4",
                "contact_number": "+91 9876543210",
                "is_active": True,
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        loc_id = data["data"]["id"]

        # 2. Get Location Details
        res_get = self.client.get(f"/api/v1/payroll/masters/locations/{loc_id}", headers=self.headers)
        self.assertEqual(res_get.status_code, 200)
        self.assertEqual(res_get.json()["data"]["name"], "Pune Innovation Hub")

        # 3. Update Location
        res_put = self.client.put(
            f"/api/v1/payroll/masters/locations/{loc_id}",
            headers=self.headers,
            json={"city": "Pimpri-Chinchwad", "address": "Hinjawadi Phase 1"},
        )
        self.assertEqual(res_put.status_code, 200)
        self.assertEqual(res_put.json()["data"]["city"], "Pimpri-Chinchwad")

        # 4. Create an employee assigned to this location
        emp = Student(
            tenant_id=self.tenant.id,
            roll_number="EMP-LOC-TEST-01",
            name="Rohit Sharma",
            department="Engineering",
            user_role="employee",
            location_id=loc_id,
            is_active=True,
        )
        self.db.add(emp)
        self.db.commit()
        self.db.refresh(emp)

        # 5. Attempt Delete Location -> Must fail with 400 because active employee is assigned (Rule 1 A)
        res_del_fail = self.client.delete(f"/api/v1/payroll/masters/locations/{loc_id}", headers=self.headers)
        self.assertEqual(res_del_fail.status_code, 400)
        self.assertIn("employee(s) are currently assigned", res_del_fail.json()["detail"])

        # 6. Unassign employee and delete Location -> Must succeed
        emp.location_id = None
        self.db.commit()

        res_del_ok = self.client.delete(f"/api/v1/payroll/masters/locations/{loc_id}", headers=self.headers)
        self.assertEqual(res_del_ok.status_code, 200)
        self.assertEqual(res_del_ok.json()["status"], "success")

        # Verify not found
        res_check = self.client.get(f"/api/v1/payroll/masters/locations/{loc_id}", headers=self.headers)
        self.assertEqual(res_check.status_code, 404)

        # Clean up test emp
        self.db.delete(emp)
        self.db.commit()

    def test_02_designations_crud_and_delete_protection(self):
        """Test Designation Master full CRUD and employee assignment delete protection (1 A)."""
        # 1. Create Designation
        res = self.client.post(
            "/api/v1/payroll/masters/designations",
            headers=self.headers,
            json={
                "title": "Principal Architect",
                "code": "PR-ARCH",
                "description": "Technical design lead across projects",
                "is_active": True,
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        desig_id = data["data"]["id"]

        # 2. Get Designation Details
        res_get = self.client.get(f"/api/v1/payroll/masters/designations/{desig_id}", headers=self.headers)
        self.assertEqual(res_get.status_code, 200)
        self.assertEqual(res_get.json()["data"]["title"], "Principal Architect")

        # 3. Update Designation
        res_put = self.client.put(
            f"/api/v1/payroll/masters/designations/{desig_id}",
            headers=self.headers,
            json={"description": "Senior Technical Director"},
        )
        self.assertEqual(res_put.status_code, 200)
        self.assertEqual(res_put.json()["data"]["description"], "Senior Technical Director")

        # 4. Create an employee assigned to this designation
        emp = Student(
            tenant_id=self.tenant.id,
            roll_number="EMP-DESIG-TEST-01",
            name="Anita Desai",
            department="Technology",
            user_role="employee",
            designation_id=desig_id,
            designation="Principal Architect",
            is_active=True,
        )
        self.db.add(emp)
        self.db.commit()
        self.db.refresh(emp)

        # 5. Attempt Delete Designation -> Must fail with 400 because active employee is assigned (Rule 1 A)
        res_del_fail = self.client.delete(f"/api/v1/payroll/masters/designations/{desig_id}", headers=self.headers)
        self.assertEqual(res_del_fail.status_code, 400)
        self.assertIn("employee(s) are currently assigned", res_del_fail.json()["detail"])

        # 6. Unassign employee and delete Designation -> Must succeed
        emp.designation_id = None
        self.db.commit()

        res_del_ok = self.client.delete(f"/api/v1/payroll/masters/designations/{desig_id}", headers=self.headers)
        self.assertEqual(res_del_ok.status_code, 200)
        self.assertEqual(res_del_ok.json()["status"], "success")

        # Verify not found
        res_check = self.client.get(f"/api/v1/payroll/masters/designations/{desig_id}", headers=self.headers)
        self.assertEqual(res_check.status_code, 404)

        # Clean up test emp
        self.db.delete(emp)
        self.db.commit()

    def test_03_salary_templates_crud_and_delete_protection(self):
        """Test Salary Template full CRUD and structure assignment delete protection (2 A)."""
        # 1. Create Salary Template
        res = self.client.post(
            "/api/v1/payroll/masters/templates",
            headers=self.headers,
            json={
                "name": "Mid-Level Engineer Package",
                "code": "MLE-PKG-01",
                "compensation_model": "STRUCTURED_SALARY",
                "description": "Base salary package for software engineers",
                "basic_percentage": 50.0,
                "hra_percentage": 20.0,
                "da_percentage": 0.0,
                "conveyance_fixed": 1600.0,
                "medical_fixed": 1250.0,
                "enable_pf": True,
                "pf_capped_at_ceiling": True,
                "enable_esi": True,
                "enable_pt": True,
                "is_active": True,
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        tpl_id = data["data"]["id"]

        # 2. Get Template Details
        res_get = self.client.get(f"/api/v1/payroll/masters/templates/{tpl_id}", headers=self.headers)
        self.assertEqual(res_get.status_code, 200)
        self.assertEqual(res_get.json()["data"]["name"], "Mid-Level Engineer Package")

        # 3. Update Template
        res_put = self.client.put(
            f"/api/v1/payroll/masters/templates/{tpl_id}",
            headers=self.headers,
            json={"hra_percentage": 25.0, "conveyance_fixed": 2000.0},
        )
        self.assertEqual(res_put.status_code, 200)
        self.assertEqual(res_put.json()["data"]["hra_percentage"], 25.0)

        # 4. Create an employee and assign active salary structure using this template
        emp = Student(
            tenant_id=self.tenant.id,
            roll_number="EMP-TPL-TEST-01",
            name="Vikas Gupta",
            department="Engineering",
            user_role="employee",
            is_active=True,
        )
        self.db.add(emp)
        self.db.commit()
        self.db.refresh(emp)

        struct = EmployeeSalaryStructure(
            tenant_id=self.tenant.id,
            student_id=emp.id,
            template_id=tpl_id,
            compensation_model="STRUCTURED_SALARY",
            annual_ctc=600000.0,
            monthly_gross=50000.0,
            monthly_basic=25000.0,
            monthly_hra=12500.0,
            conveyance_allowance=2000.0,
            medical_allowance=1250.0,
            special_allowance=9250.0,
            enable_pf=True,
            enable_esi=False,
            enable_pt=True,
            effective_from_date="2026-04-01",
            is_current=True,
        )
        self.db.add(struct)
        self.db.commit()

        # 5. Attempt Delete Template -> Must fail with 400 because active structure is assigned (Rule 2 A)
        res_del_fail = self.client.delete(f"/api/v1/payroll/masters/templates/{tpl_id}", headers=self.headers)
        self.assertEqual(res_del_fail.status_code, 400)
        self.assertIn("actively using it", res_del_fail.json()["detail"])

        # 6. Deactivate / remove structure and delete Template -> Must succeed
        self.db.delete(struct)
        self.db.commit()

        res_del_ok = self.client.delete(f"/api/v1/payroll/masters/templates/{tpl_id}", headers=self.headers)
        self.assertEqual(res_del_ok.status_code, 200)
        self.assertEqual(res_del_ok.json()["status"], "success")

        # Verify not found
        res_check = self.client.get(f"/api/v1/payroll/masters/templates/{tpl_id}", headers=self.headers)
        self.assertEqual(res_check.status_code, 404)

        # Clean up test emp
        self.db.delete(emp)
        self.db.commit()

    def test_04_enrollment_and_profile_update_with_masters(self):
        """Test employee enrollment & profile updating with Location & Designation (Rule 3 A)."""
        # Create test Location and Designation
        loc = CompanyLocation(
            tenant_id=self.tenant.id,
            name="Bangalore Center",
            code="BLR-01",
            city="Bengaluru",
            state="Karnataka",
            is_active=True,
        )
        desig = DesignationMaster(
            tenant_id=self.tenant.id,
            title="Senior DevOps Engineer",
            code="SR-DEVOPS",
            is_active=True,
        )
        self.db.add(loc)
        self.db.add(desig)
        self.db.commit()
        self.db.refresh(loc)
        self.db.refresh(desig)

        # 1. Register employee via /api/v1/enroll/student with location_id & designation_id
        res_reg = self.client.post(
            "/api/v1/enroll/student",
            headers=self.headers,
            json={
                "roll_number": "EMP-SYNC-01",
                "name": "Kavita Rao",
                "department": "Infrastructure",
                "user_role": "employee",
                "location_id": loc.id,
                "designation_id": desig.id,
                "designation": desig.title,
                "date_of_joining": "2026-05-01",
            },
        )
        self.assertEqual(res_reg.status_code, 200)
        emp_id = res_reg.json()["student"]["id"]

        # Verify persisted fields
        self.db.rollback()
        emp_record = self.db.query(Student).filter(Student.id == emp_id).first()
        self.assertIsNotNone(emp_record)
        self.assertEqual(emp_record.location_id, loc.id)
        self.assertEqual(emp_record.designation_id, desig.id)
        self.assertEqual(emp_record.designation, "Senior DevOps Engineer")

        # 2. Update employee profile via PUT /api/v1/enroll/student/{id}
        res_upd = self.client.put(
            f"/api/v1/enroll/student/{emp_id}",
            headers=self.headers,
            json={
                "roll_number": "EMP-SYNC-01",
                "name": "Kavita Rao",
                "department": "Infrastructure & Cloud",
                "user_role": "employee",
                "location_id": None,
                "designation_id": desig.id,
                "hourly_rate": 450.0,
            },
        )
        self.assertEqual(res_upd.status_code, 200)

        self.db.rollback()
        emp_record = self.db.query(Student).filter(Student.id == emp_id).first()
        self.assertIsNone(emp_record.location_id)
        self.assertEqual(emp_record.designation_id, desig.id)

        # Clean up
        self.db.delete(emp_record)
        self.db.delete(loc)
        self.db.delete(desig)
        self.db.commit()


if __name__ == "__main__":
    unittest.main()
