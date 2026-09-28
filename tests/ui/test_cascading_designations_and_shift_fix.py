"""
Test Suite: Cascading Designation Dropdowns, Default Shift Fallback & Registration Toast
Verifies:
1. /enroll page renders ENROLL_DESIGNATIONS in client JS cache and data-dept-id attributes on options.
2. /enroll page work shift select does not block HTML5 submission when no custom shifts exist.
3. Employee registration via POST /api/v1/enroll/student succeeds when shift_id is None / default.
4. /employees page edit modal contains data-dept-id attributes on designation options for dynamic cascading filtering.
5. Batch enrollment via POST /api/v1/enroll/batch-upload succeeds when shift_id is None / default.
"""

import io
import unittest
from PIL import Image
from fastapi.testclient import TestClient
from src.server.app import app
from src.database.session import SessionLocal
from src.database.models import Tenant, User, Student, Department, DesignationMaster, WorkShift
from src.utils.auth_utils import hash_password
from src.server.rbac_middleware import create_access_token


def create_dummy_image():
    file = io.BytesIO()
    image = Image.new("RGB", (100, 100), color=(73, 109, 137))
    image.save(file, "jpeg")
    file.seek(0)
    return file


class TestCascadingDesignationsAndShiftFix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db = SessionLocal()

        # Create a dedicated Corporate Tenant with no initial custom shifts
        cls.corp_tenant = cls.db.query(Tenant).filter(Tenant.slug == "test-cascade-corp").first()
        if not cls.corp_tenant:
            cls.corp_tenant = Tenant(
                name="Cascade Tech Ltd",
                slug="test-cascade-corp",
                tenant_type="corporate",
                subscription_plan="SMART",
                is_active=True,
                is_deleted=False,
            )
            cls.db.add(cls.corp_tenant)
            cls.db.flush()

            # Create Admin User
            cls.corp_admin = User(
                username="admin_cascade",
                email="admin_cascade@example.com",
                password_hash=hash_password("admin123"),
                full_name="Cascade Admin",
                role="TENANT_ADMIN",
                tenant_id=cls.corp_tenant.id,
                is_active=True,
            )
            cls.db.add(cls.corp_admin)

            # Create 2 Departments
            cls.dept_eng = Department(name="Engineering", code="ENG", tenant_id=cls.corp_tenant.id)
            cls.dept_sales = Department(name="Sales & Marketing", code="SALES", tenant_id=cls.corp_tenant.id)
            cls.db.add_all([cls.dept_eng, cls.dept_sales])
            cls.db.flush()

            # Create Designations (one in ENG, one in SALES, one Global unassigned)
            cls.desig_eng = DesignationMaster(
                title="Software Engineer",
                code="SWE",
                department_id=cls.dept_eng.id,
                tenant_id=cls.corp_tenant.id,
                is_active=True,
            )
            cls.desig_sales = DesignationMaster(
                title="Sales Executive",
                code="SE",
                department_id=cls.dept_sales.id,
                tenant_id=cls.corp_tenant.id,
                is_active=True,
            )
            cls.desig_global = DesignationMaster(
                title="General Intern",
                code="INT",
                department_id=None,
                tenant_id=cls.corp_tenant.id,
                is_active=True,
            )
            cls.db.add_all([cls.desig_eng, cls.desig_sales, cls.desig_global])
            cls.db.commit()
        else:
            cls.corp_admin = cls.db.query(User).filter(User.username == "admin_cascade").first()
            cls.dept_eng = cls.db.query(Department).filter(Department.tenant_id == cls.corp_tenant.id, Department.code == "ENG").first()
            cls.dept_sales = cls.db.query(Department).filter(Department.tenant_id == cls.corp_tenant.id, Department.code == "SALES").first()
            cls.desig_eng = cls.db.query(DesignationMaster).filter(DesignationMaster.tenant_id == cls.corp_tenant.id, DesignationMaster.code == "SWE").first()
            cls.desig_sales = cls.db.query(DesignationMaster).filter(DesignationMaster.tenant_id == cls.corp_tenant.id, DesignationMaster.code == "SE").first()
            cls.desig_global = cls.db.query(DesignationMaster).filter(DesignationMaster.tenant_id == cls.corp_tenant.id, DesignationMaster.code == "INT").first()

        # Clean up any leftover test students
        cls.db.query(Student).filter(Student.tenant_id == cls.corp_tenant.id).delete(synchronize_session=False)
        cls.db.commit()

        cls.token = create_access_token(
            user_id=cls.corp_admin.id,
            role=cls.corp_admin.role,
            tenant_id=cls.corp_tenant.id,
            username=cls.corp_admin.username,
        )
        cls.headers = {"Authorization": f"Bearer {cls.token}"}
        cls.cookies = {"access_token": cls.token, "active_tenant_id": str(cls.corp_tenant.id)}

    @classmethod
    def tearDownClass(cls):
        try:
            cls.db.query(Student).filter(Student.tenant_id == cls.corp_tenant.id).delete(synchronize_session=False)
            cls.db.commit()
        except Exception:
            pass
        cls.db.close()

    def test_01_enroll_page_renders_designation_cache_and_data_dept_id(self):
        """Verify GET /enroll renders ENROLL_DESIGNATIONS and data-dept-id attributes on options."""
        res = self.client.get("/enroll", cookies=self.cookies)
        self.assertEqual(res.status_code, 200)
        content = res.text

        # 1. Check ENROLL_DESIGNATIONS is embedded in script block
        self.assertIn("const ENROLL_DESIGNATIONS =", content)

        # 2. Check data-dept-id attributes on designation options
        self.assertIn(f'data-dept-id="{self.dept_eng.id}"', content)
        self.assertIn(f'data-dept-id="{self.dept_sales.id}"', content)
        self.assertIn('data-dept-id=""', content)

        # 3. Check that work shift select does NOT have blocking 'required' when no custom shifts exist
        self.assertIn('<select id="enrollShiftSelect" class="form-control">', content)
        self.assertIn('<select id="batchEnrollShiftSelect" class="form-control">', content)

    def test_02_employees_directory_renders_designation_data_dept_id(self):
        """Verify GET /employees renders data-dept-id on edit modal designation options."""
        res = self.client.get("/employees", cookies=self.cookies)
        self.assertEqual(res.status_code, 200)
        content = res.text

        # Check edit modal select contains data-dept-id attributes
        self.assertIn('id="editDesignationSelect"', content)
        self.assertIn(f'data-dept-id="{self.dept_eng.id}"', content)
        self.assertIn(f'data-dept-id="{self.dept_sales.id}"', content)

    def test_03_employee_registration_with_default_shift_succeeds(self):
        """Verify employee registration succeeds with shift_id=None (default shift fallback)."""
        payload = {
            "roll_number": "EMP-CASCADE-01",
            "name": "Alex Mercer",
            "department_id": self.dept_eng.id,
            "department": "Engineering",
            "designation_id": self.desig_eng.id,
            "designation": "Software Engineer",
            "user_role": "employee",
            "shift_id": None,  # System default fallback
            "date_of_joining": "2026-09-01",
            "email": "alex.mercer@cascadetech.com",
        }
        res = self.client.post("/api/v1/enroll/student", json=payload, headers=self.headers, cookies=self.cookies)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("student", data)
        self.assertEqual(data["student"]["name"], "Alex Mercer")
        self.assertEqual(data["student"]["department_id"], self.dept_eng.id)
        self.assertEqual(data["student"]["designation_id"], self.desig_eng.id)

    def test_04_batch_upload_with_default_shift_succeeds(self):
        """Verify batch upload enrollment succeeds with shift_id=None (default shift fallback)."""
        img1 = create_dummy_image()
        img2 = create_dummy_image()
        img3 = create_dummy_image()

        files = [
            ("photo_front", ("front.jpg", img1, "image/jpeg")),
            ("photo_left", ("left.jpg", img2, "image/jpeg")),
            ("photo_right", ("right.jpg", img3, "image/jpeg")),
        ]
        data = {
            "roll_number": "EMP-CASCADE-02",
            "name": "Jane Hopper",
            "department_id": str(self.dept_sales.id),
            "department": "Sales & Marketing",
            "designation_id": str(self.desig_sales.id),
            "designation": "Sales Executive",
            "user_role": "employee",
            "date_of_joining": "2026-09-01",
            "email": "jane.hopper@cascadetech.com",
            # shift_id omitted to test default fallback
        }
        from unittest.mock import patch
        import numpy as np

        with patch("src.server.routes.api_enrollment.evaluate_image_quality", return_value=(True, "OK")), \
             patch("src.server.routes.api_enrollment.FaceEngine.compute_single_face_vector", return_value=(np.zeros(128, dtype=np.float32), (10, 90, 90, 10), "OK")):
            res = self.client.post("/api/v1/enroll/batch-upload", data=data, files=files, headers=self.headers, cookies=self.cookies)

        self.assertEqual(res.status_code, 200)
        resp_data = res.json()
        self.assertIn("student", resp_data)
        self.assertEqual(resp_data["student"]["name"], "Jane Hopper")
        self.assertEqual(resp_data["student"]["department_id"], self.dept_sales.id)
        self.assertEqual(resp_data["student"]["designation_id"], self.desig_sales.id)

    def test_05_employees_directory_renders_all_tenant_designations_cache(self):
        """Verify GET /employees renders window.allTenantDesignations and other master data in script block."""
        res = self.client.get("/employees", cookies=self.cookies)
        self.assertEqual(res.status_code, 200)
        content = res.text

        self.assertIn("window.allTenantDesignations =", content)
        self.assertIn("window.allTenantWorkShifts =", content)
        self.assertIn("window.allTenantDepartments =", content)
        self.assertIn("window.allTenantStudents =", content)

    def test_06_employee_edit_persists_department_designation_and_doj(self):
        """Verify PUT /api/v1/enroll/student/{id} updates employee details and persists them to DB."""
        # 1. First register employee
        payload = {
            "roll_number": "EMP-EDIT-01",
            "name": "Bruce Banner",
            "department_id": self.dept_eng.id,
            "department": "Engineering",
            "designation_id": self.desig_eng.id,
            "designation": "Software Engineer",
            "user_role": "employee",
            "date_of_joining": "2025-01-15",
            "email": "bruce.banner@cascadetech.com",
        }
        res = self.client.post("/api/v1/enroll/student", json=payload, headers=self.headers, cookies=self.cookies)
        self.assertEqual(res.status_code, 200)
        s_id = res.json()["student"]["id"]

        # 2. Update employee to Sales & Marketing and Sales Executive designation
        update_payload = {
            "roll_number": "EMP-EDIT-01",
            "name": "Dr. Bruce Banner",
            "department_id": self.dept_sales.id,
            "department": "Sales & Marketing",
            "designation_id": self.desig_sales.id,
            "designation": "Sales Executive",
            "user_role": "employee",
            "date_of_joining": "2025-02-01",
            "email": "dr.bruce@cascadetech.com",
        }
        res_put = self.client.put(f"/api/v1/enroll/student/{s_id}", json=update_payload, headers=self.headers, cookies=self.cookies)
        self.assertEqual(res_put.status_code, 200)
        put_data = res_put.json()
        self.assertEqual(put_data["student"]["name"], "Dr. Bruce Banner")
        self.assertEqual(put_data["student"]["department_id"], self.dept_sales.id)
        self.assertEqual(put_data["student"]["designation_id"], self.desig_sales.id)
        self.assertEqual(put_data["student"]["date_of_joining"], "2025-02-01")
        self.assertEqual(put_data["student"]["email"], "dr.bruce@cascadetech.com")

        # 3. Verify direct fetch from GET /api/v1/enroll/student/{id}
        res_get = self.client.get(f"/api/v1/enroll/student/{s_id}", headers=self.headers, cookies=self.cookies)
        self.assertEqual(res_get.status_code, 200)
        get_data = res_get.json()
        self.assertEqual(get_data["student"]["name"], "Dr. Bruce Banner")
        self.assertEqual(get_data["student"]["department_id"], self.dept_sales.id)
        self.assertEqual(get_data["student"]["designation_id"], self.desig_sales.id)
        self.assertEqual(get_data["student"]["date_of_joining"], "2025-02-01")

    def test_07_employee_relieve_and_reinstate_actions(self):
        """Verify relieving and reinstating directory action endpoints."""
        # Create an employee
        payload = {
            "roll_number": "EMP-RELIEVE-01",
            "name": "Tony Stark",
            "department_id": self.dept_eng.id,
            "department": "Engineering",
            "designation_id": self.desig_eng.id,
            "user_role": "employee",
        }
        res = self.client.post("/api/v1/enroll/student", json=payload, headers=self.headers, cookies=self.cookies)
        self.assertEqual(res.status_code, 200)
        s_id = res.json()["student"]["id"]

        # Relieve
        rel_res = self.client.post(
            f"/api/v1/enroll/student/{s_id}/relieve",
            json={"reason": "Project Completed", "employment_status": "RELIEVED", "relieved_at": "2026-09-20"},
            headers=self.headers,
            cookies=self.cookies,
        )
        self.assertEqual(rel_res.status_code, 200)

        # Verify inactive status
        get_res = self.client.get(f"/api/v1/enroll/student/{s_id}", headers=self.headers, cookies=self.cookies)
        self.assertEqual(get_res.json()["student"]["employment_status"], "RELIEVED")

        # Reinstate
        rein_res = self.client.post(
            f"/api/v1/enroll/student/{s_id}/reinstate",
            json={"reason": "Re-hired"},
            headers=self.headers,
            cookies=self.cookies,
        )
        self.assertEqual(rein_res.status_code, 200)
        get_res2 = self.client.get(f"/api/v1/enroll/student/{s_id}", headers=self.headers, cookies=self.cookies)
        self.assertEqual(get_res2.json()["student"]["employment_status"], "ACTIVE")

    def test_08_directory_grid_and_filters_role_replacement_with_designation(self):
        """Verify Role column & filter are replaced by Designation in corporate tenant views."""
        # 1. Check corporate /employees view
        res = self.client.get("/employees", cookies=self.cookies)
        self.assertEqual(res.status_code, 200)
        content = res.text

        # Column Header: Designation
        self.assertIn("<th>Designation</th>", content)
        # Cascading Filter Dropdown: dirDesigFilter
        self.assertIn('id="dirDesigFilter"', content)
        self.assertNotIn('id="dirRoleFilter"', content)
        # Dropdown options contain data-dept-id
        self.assertIn(f'data-dept-id="{self.dept_eng.id}"', content)
        # Row badge displays Designation
        self.assertIn("stdDesigBadge", content)
        self.assertIn("Software Engineer", content)
        # Table row has data-desig-id
        self.assertIn("data-desig-id=", content)

        # 2. Check educational /students view using default tenant (slug='default')
        edu_user = self.db.query(User).filter(User.username == "admin", User.tenant_id == 1).first()
        if edu_user:
            edu_token = create_access_token(user_id=edu_user.id, role=edu_user.role, tenant_id=1, username=edu_user.username)
            edu_cookies = {"access_token": edu_token, "active_tenant_id": "1"}
            res_edu = self.client.get("/students", cookies=edu_cookies)
            self.assertEqual(res_edu.status_code, 200)
            edu_content = res_edu.text
            # Educational view preserves Role
            self.assertIn("<th>Role</th>", edu_content)
            self.assertIn('id="dirRoleFilter"', edu_content)
            self.assertNotIn('id="dirDesigFilter"', edu_content)

    def test_09_transfer_modal_elements_and_department_designation_transfer(self):
        """Verify transfer modal HTML elements and department transfer API with designation update."""
        # 1. Check HTML elements in /employees view
        res = self.client.get("/employees", cookies=self.cookies)
        self.assertEqual(res.status_code, 200)
        content = res.text

        # Modal elements
        self.assertIn('id="transferEmployeeModal"', content)
        self.assertIn('id="transferTargetDept"', content)
        self.assertIn('id="transferTargetDesignation"', content)
        self.assertIn(f'data-dept-id="{self.dept_eng.id}"', content)
        self.assertIn(f'data-dept-id="{self.dept_sales.id}"', content)
        self.assertIn('id="btnConfirmTransfer"', content)
        self.assertIn('class="btn btn-primary"', content)

        # 2. Register an employee in Engineering
        payload = {
            "roll_number": "EMP-XFER-01",
            "name": "Steve Rogers",
            "department_id": self.dept_eng.id,
            "department": "Engineering",
            "designation_id": self.desig_eng.id,
            "designation": "Software Engineer",
            "user_role": "employee",
        }
        res_create = self.client.post("/api/v1/enroll/student", json=payload, headers=self.headers, cookies=self.cookies)
        self.assertEqual(res_create.status_code, 200)
        s_id = res_create.json()["student"]["id"]

        # 3. Transfer employee to Sales department with Sales Executive designation
        xfer_payload = {
            "department_id": self.dept_sales.id,
            "designation_id": self.desig_sales.id,
            "designation": "Sales Executive",
        }
        res_xfer = self.client.post(
            f"/api/v1/enroll/student/{s_id}/transfer-department",
            json=xfer_payload,
            headers=self.headers,
            cookies=self.cookies,
        )
        self.assertEqual(res_xfer.status_code, 200)
        xfer_data = res_xfer.json()
        self.assertEqual(xfer_data["status"], "success")

        # 4. Verify employee's updated department and designation in database
        res_get = self.client.get(f"/api/v1/enroll/student/{s_id}", headers=self.headers, cookies=self.cookies)
        self.assertEqual(res_get.status_code, 200)
        get_data = res_get.json()["student"]
        self.assertEqual(get_data["department_id"], self.dept_sales.id)
        self.assertEqual(get_data["designation_id"], self.desig_sales.id)
        self.assertEqual(get_data["designation"], "Sales Executive")

    def test_10_retake_photos_modal_elements_and_update_photos_api(self):
        """Verify retake photos modal HTML elements and update-photos API with 3 photos."""
        # 1. Check HTML elements in /employees view
        res = self.client.get("/employees", cookies=self.cookies)
        self.assertEqual(res.status_code, 200)
        content = res.text

        # Modal elements
        self.assertIn('id="retakePhotosModal"', content)
        self.assertIn('id="retakeCaptureCanvas"', content)
        self.assertIn('id="btnRetakeCapFrontal"', content)
        self.assertIn('id="btnRetakeCapLeft"', content)
        self.assertIn('id="btnRetakeCapRight"', content)
        self.assertIn('id="btnToggleRetakeCam"', content)
        self.assertIn('id="btnSubmitRetakeUpload"', content)
        self.assertIn('id="retakeCamFeedback"', content)
        self.assertIn('id="retakeResultAlert"', content)

        # 2. Register an employee for photo retake
        payload = {
            "roll_number": "EMP-RETAKE-01",
            "name": "Natasha Romanoff",
            "department_id": self.dept_eng.id,
            "department": "Engineering",
            "designation_id": self.desig_eng.id,
            "designation": "Software Engineer",
            "user_role": "employee",
        }
        res_create = self.client.post("/api/v1/enroll/student", json=payload, headers=self.headers, cookies=self.cookies)
        self.assertEqual(res_create.status_code, 200)
        s_id = res_create.json()["student"]["id"]

        # 3. Submit 3 new photos via update-photos endpoint
        img1 = create_dummy_image()
        img2 = create_dummy_image()
        img3 = create_dummy_image()

        files = [
            ("photo_front", ("retake_front.jpg", img1, "image/jpeg")),
            ("photo_left", ("retake_left.jpg", img2, "image/jpeg")),
            ("photo_right", ("retake_right.jpg", img3, "image/jpeg")),
        ]

        from unittest.mock import patch
        import numpy as np

        with patch("src.server.routes.api_enrollment.evaluate_image_quality", return_value=(True, "OK")), \
             patch("src.server.routes.api_enrollment.FaceEngine.compute_single_face_vector", return_value=(np.ones(128, dtype=np.float32), (10, 90, 90, 10), "OK")):
            res_upd = self.client.post(
                f"/api/v1/enroll/student/{s_id}/update-photos",
                files=files,
                headers=self.headers,
                cookies=self.cookies,
            )

        self.assertEqual(res_upd.status_code, 200)
        upd_data = res_upd.json()
        self.assertEqual(upd_data["status"], "success")
        self.assertIn("Updated photo angles", upd_data["message"])


if __name__ == "__main__":
    unittest.main()

