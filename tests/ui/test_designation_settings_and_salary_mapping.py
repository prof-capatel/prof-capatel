"""
Unit & Integration Tests for:
1. Employee form label renaming & user role redundancy cleanup.
2. Designation management in General Settings (/settings -> Designations & Roles tab).
3. Designation & Salary Structure Mappings in Payroll Masters (/payroll).
4. Tenant-scoped Designation CRUD API functionality without requiring special payroll flags.
"""
import sys
import os
from pathlib import Path
import unittest
from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.database.session import get_db, init_db
from src.database.models import Tenant, User, DesignationMaster
from src.server.app import app
from src.server.rbac_middleware import create_access_token


class TestDesignationSettingsAndSalaryMapping(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)
        cls.db = next(get_db())

    def _get_auth_client(self, tenant_slug: str):
        tenant = self.db.query(Tenant).filter(Tenant.slug == tenant_slug).first()
        self.assertIsNotNone(tenant, f"Tenant {tenant_slug} must exist")
        if tenant.subscription_plan != "PRO":
            tenant.subscription_plan = "PRO"
            self.db.commit()
            self.db.refresh(tenant)
        admin_u = self.db.query(User).filter(User.tenant_id == tenant.id, User.role == "TENANT_ADMIN", User.is_active == True).first()
        self.assertIsNotNone(admin_u, f"Admin for {tenant_slug} must exist")

        token = create_access_token(
            user_id=admin_u.id, role="TENANT_ADMIN", tenant_id=admin_u.tenant_id, username=admin_u.username
        )
        client = TestClient(app)
        client.cookies.set("access_token", token)
        client.cookies.set("active_tenant_slug", tenant_slug)
        client.cookies.set("active_tenant_id", str(tenant.id))
        client.headers["X-Tenant-ID"] = str(tenant.id)
        return client, tenant

    def test_01_enroll_page_labels_and_role_deduplication(self):
        """Verify enroll.html uses updated labels and removes duplicate visible user role for corporate."""
        client, tenant = self._get_auth_client("the-retail-store")
        res = client.get("/enroll")
        self.assertEqual(res.status_code, 200)
        html = res.text

        # Field labels
        self.assertIn("Salary Structure", html)
        self.assertIn("Work shift", html)
        self.assertIn("Designation", html)
        self.assertNotIn("Designation / Role Title", html)
        self.assertNotIn("Compensation Salary Template", html)

        # Hidden input for corporate userRole
        self.assertIn('<input type="hidden" id="userRole" value="employee">', html)
        self.assertIn('<input type="hidden" id="batchUserRole" value="employee">', html)

        # Designation dropdown is present
        self.assertIn('id="enrollDesignationSelect"', html)
        self.assertIn('id="batchEnrollDesignationSelect"', html)

    def test_02_students_page_edit_modal_labels(self):
        """Verify students.html edit modal uses updated labels."""
        client, tenant = self._get_auth_client("the-retail-store")
        res = client.get("/students")
        self.assertEqual(res.status_code, 200)
        html = res.text

        self.assertIn("Salary Structure", html)
        self.assertIn("Work shift", html)
        self.assertIn("Designation", html)

    def test_03_settings_page_designations_tab_and_modal(self):
        """Verify settings.html includes Designations & Roles tab and modal without salary template field."""
        client, tenant = self._get_auth_client("the-retail-store")
        res = client.get("/settings")
        self.assertEqual(res.status_code, 200)
        html = res.text

        # Tab button and pane
        self.assertIn('id="tabBtnDesignations"', html)
        self.assertIn('id="tabContentDesignations"', html)
        self.assertIn("Designations", html)
        self.assertIn("openAddDesignationModal()", html)

        # Modal elements
        self.assertIn('id="settingsDesignationModal"', html)
        self.assertIn('id="modalSettingsDesigTitle"', html)
        self.assertIn('id="modalSettingsDesigCode"', html)
        self.assertIn('id="modalSettingsDesigDept"', html)
        self.assertIn('id="modalSettingsDesigDesc"', html)
        self.assertIn('id="modalSettingsDesigIsActive"', html)

        # Modal should NOT contain salary template selection
        self.assertNotIn('id="modalSettingsDesigSalaryTemplate"', html)
        self.assertNotIn('id="stDesigSalaryTemplate"', html)

        # JS functions present
        self.assertIn("openAddDesignationModal", html)
        self.assertIn("openEditDesignationModal", html)
        self.assertIn("saveSettingsDesignationModal", html)
        self.assertIn("deleteSettingsDesignation", html)

    def test_04_payroll_masters_designation_salary_mapping_ui(self):
        """Verify payroll.html reframes designation card to mappings and uses dynamic select dropdown."""
        client, tenant = self._get_auth_client("the-retail-store")
        res = client.get("/payroll")
        self.assertEqual(res.status_code, 200)
        html = res.text

        self.assertIn("Designation &amp; Salary Structure Mappings", html)
        self.assertIn("Map organizational designations to default salary structures and compensation templates.", html)
        self.assertIn("Mapped Salary Structure", html)
        self.assertIn("Map Designation to Salary Structure", html)

        # Dropdown select & auto-populated readonly fields
        self.assertIn('id="desigModalSelect"', html)
        self.assertIn('id="desigModalCode"', html)
        self.assertIn('id="desigModalDeptName"', html)
        self.assertIn('id="desigModalSalaryTemplate"', html)
        self.assertIn('id="desigModalStatusDisplay"', html)
        self.assertNotIn('id="desigModalTitle"', html)

        # Helper note with link to Settings
        self.assertIn('href="/settings#designations"', html)

    def test_05_designation_api_crud_operations(self):
        """Verify Designation API endpoints function under tenant-scoped authorization."""
        client, tenant = self._get_auth_client("the-retail-store")

        # Clean up any leftover test designations
        self.db.query(DesignationMaster).filter(
            DesignationMaster.tenant_id == tenant.id,
            DesignationMaster.code.like("TEST-SPEC-%")
        ).delete(synchronize_session=False)
        self.db.commit()

        # 1. Create a designation
        create_payload = {
            "title": "Automated Test Specialist Dynamic",
            "code": "TEST-SPEC-01",
            "department_id": None,
            "salary_template_id": None,
            "description": "Automated testing role created during test suite execution",
            "is_active": True
        }
        res_create = client.post("/api/v1/payroll/masters/designations", json=create_payload)
        self.assertEqual(res_create.status_code, 200)
        data = res_create.json()
        self.assertEqual(data.get("status"), "success")
        created_id = data.get("data", {}).get("id")
        self.assertIsNotNone(created_id)

        # 2. Get list of designations
        res_list = client.get("/api/v1/payroll/masters/designations")
        self.assertEqual(res_list.status_code, 200)
        items = res_list.json().get("data", [])
        matching = [i for i in items if i.get("id") == created_id]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["title"], "Automated Test Specialist Dynamic")

        # 3. Update designation
        update_payload = {
            "title": "Automated Lead Test Specialist Dynamic",
            "code": "TEST-SPEC-LEAD",
            "department_id": None,
            "salary_template_id": None,
            "description": "Updated lead role",
            "is_active": True
        }
        res_update = client.put(f"/api/v1/payroll/masters/designations/{created_id}", json=update_payload)
        self.assertEqual(res_update.status_code, 200)
        self.assertEqual(res_update.json().get("data", {}).get("title"), "Automated Lead Test Specialist Dynamic")

        # 4. Delete designation
        res_delete = client.delete(f"/api/v1/payroll/masters/designations/{created_id}")
        self.assertEqual(res_delete.status_code, 200)
        self.assertEqual(res_delete.json().get("status"), "success")

    def test_06_designation_salary_mapping_and_statutory_settings(self):
        """Verify adding/editing salary template mapping on designation and statutory payroll settings."""
        client, tenant = self._get_auth_client("the-retail-store")

        # Create a test designation and test salary template
        res_tpl = client.post("/api/v1/payroll/masters/templates", json={
            "name": "Mapping Test Template",
            "code": "TPL-MAP-01",
            "compensation_model": "STRUCTURED_SALARY",
            "basic_percentage": 50.0,
            "hra_percentage": 20.0,
            "da_percentage": 0.0,
            "conveyance_fixed": 1600.0,
            "medical_fixed": 1250.0,
            "enable_pf": True,
            "enable_esi": True,
            "enable_pt": True,
            "is_active": True
        })
        self.assertEqual(res_tpl.status_code, 200)
        tpl_id = res_tpl.json().get("data", {}).get("id")
        self.assertIsNotNone(tpl_id)

        res_desig = client.post("/api/v1/payroll/masters/designations", json={
            "title": "Mapping Test Role",
            "code": "MAP-ROLE-01",
            "is_active": True
        })
        self.assertEqual(res_desig.status_code, 200)
        desig_id = res_desig.json().get("data", {}).get("id")
        self.assertIsNotNone(desig_id)

        try:
            # 1. Map template to designation (Add/Edit mapping action)
            res_map = client.put(f"/api/v1/payroll/masters/designations/{desig_id}", json={
                "salary_template_id": tpl_id
            })
            self.assertEqual(res_map.status_code, 200)
            desig_data = res_map.json().get("data", {})
            self.assertEqual(desig_data.get("salary_template_id"), tpl_id)
            self.assertEqual(desig_data.get("salary_template_name"), "Mapping Test Template")

            # 2. Clear mapping (Set to None)
            res_unmap = client.put(f"/api/v1/payroll/masters/designations/{desig_id}", json={
                "salary_template_id": None
            })
            self.assertEqual(res_unmap.status_code, 200)
            desig_data_unmapped = res_unmap.json().get("data", {})
            self.assertIsNone(desig_data_unmapped.get("salary_template_id"))
            self.assertIsNone(desig_data_unmapped.get("salary_template_name"))

            # 3. Test Payroll Settings GET & POST (ensures epf_admin_charges_pct operates without 500 error)
            res_settings_get = client.get("/api/v1/payroll/settings")
            self.assertEqual(res_settings_get.status_code, 200)
            data_cfg = res_settings_get.json().get("data", {})
            self.assertIn("epf_admin_charges_pct", data_cfg)
            self.assertEqual(data_cfg.get("epf_admin_charges_pct"), 0.50)

            res_settings_post = client.post("/api/v1/payroll/settings", json={
                "epf_admin_charges_pct": 0.50,
                "epf_employee_pct": 12.0,
                "epf_employer_pct": 12.0,
                "epf_wage_ceiling": 15000.0,
                "enable_pf_ceiling": True,
                "esi_employee_pct": 0.75,
                "esi_employer_pct": 3.25,
                "esi_gross_threshold": 21000.0,
                "pt_monthly_default": 200.0,
                "overtime_rate_multiplier": 1.5,
                "holiday_ot_multiplier": 2.0
            })
            self.assertEqual(res_settings_post.status_code, 200)
            self.assertEqual(res_settings_post.json().get("config", {}).get("epf_admin_charges_pct"), 0.50)

        finally:
            client.delete(f"/api/v1/payroll/masters/designations/{desig_id}")
            client.delete(f"/api/v1/payroll/masters/templates/{tpl_id}")

    def test_07_department_crud_and_live_listing(self):
        """Test department listing returns employee_count, create, update, delete, and settings rendering."""
        client, tenant = self._get_auth_client("ssec")

        # 1. Create a test department
        res_create = client.post("/api/v1/academic/departments", json={
            "name": "Live Refresh Testing Dept",
            "code": "LRTD",
            "description": "Test Department for Dynamic UI Refresh"
        })
        self.assertEqual(res_create.status_code, 200)
        dept_data = res_create.json().get("department", {})
        dept_id = dept_data.get("id")
        self.assertIsNotNone(dept_id)

        try:
            # 2. List departments and check employee_count is present
            res_list = client.get("/api/v1/academic/departments")
            self.assertEqual(res_list.status_code, 200)
            depts = res_list.json().get("departments", [])
            matching = [d for d in depts if d.get("id") == dept_id]
            self.assertEqual(len(matching), 1)
            self.assertIn("employee_count", matching[0])
            self.assertEqual(matching[0]["name"], "Live Refresh Testing Dept")

            # 3. Update department
            res_update = client.put(f"/api/v1/academic/departments/{dept_id}", json={
                "name": "Live Refresh Testing Dept Updated",
                "code": "LRTU",
                "description": "Updated Description"
            })
            self.assertEqual(res_update.status_code, 200)
            self.assertEqual(res_update.json().get("department", {}).get("name"), "Live Refresh Testing Dept Updated")

            # 4. Check /settings page renders the department in HTML
            res_settings = client.get("/settings")
            self.assertEqual(res_settings.status_code, 200)
            self.assertIn("Live Refresh Testing Dept Updated", res_settings.text)

        finally:
            # 5. Delete department
            res_del = client.delete(f"/api/v1/academic/departments/{dept_id}")
            self.assertEqual(res_del.status_code, 200)


if __name__ == "__main__":
    unittest.main()

