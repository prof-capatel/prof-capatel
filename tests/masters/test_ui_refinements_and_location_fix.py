import unittest
from fastapi.testclient import TestClient
from src.server.app import app
from src.database.session import get_db, SessionLocal
from src.database.models import Tenant, CompanyLocation, SalaryTemplate, Student

class TestUiRefinementsAndLocationFix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db = SessionLocal()
        cls.tenant = cls.db.query(Tenant).filter(Tenant.tenant_type.in_(["corporate", "company"])).first()
        if not cls.tenant:
            cls.tenant = Tenant(
                name="Test Corporate Tenant Refinements",
                subdomain="testcorp_refine",
                tenant_type="corporate",
                is_active=True
            )
            cls.db.add(cls.tenant)
            cls.db.commit()
            cls.db.refresh(cls.tenant)
        cls.created_location_ids = []
        cls.created_template_ids = []

    @classmethod
    def tearDownClass(cls):
        db = SessionLocal()
        if cls.created_location_ids:
            db.query(CompanyLocation).filter(CompanyLocation.id.in_(cls.created_location_ids)).delete(synchronize_session=False)
        if cls.created_template_ids:
            db.query(SalaryTemplate).filter(SalaryTemplate.id.in_(cls.created_template_ids)).delete(synchronize_session=False)
        db.commit()
        db.close()
        cls.db.close()

    def test_01_location_crud_lifecycle(self):
        """Test complete CRUD lifecycle for CompanyLocation master."""
        headers = {"X-Tenant-ID": str(self.tenant.id)}
        
        # 1. Create Location
        loc_payload = {
            "name": "Test Cyber Hub Branch",
            "code": "CYBER-01",
            "city": "Gurugram",
            "state": "Haryana",
            "contact_number": "+91 9999888877",
            "address": "DLF Cyber City, Tower B",
            "is_active": True
        }
        res = self.client.post("/api/v1/payroll/masters/locations", json=loc_payload, headers=headers)
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertEqual(data["status"], "success")
        loc_id = data["data"]["id"]
        self.created_location_ids.append(loc_id)
        self.assertEqual(data["data"]["name"], "Test Cyber Hub Branch")
        self.assertEqual(data["data"]["code"], "CYBER-01")

        # 2. Get Location
        get_res = self.client.get(f"/api/v1/payroll/masters/locations/{loc_id}", headers=headers)
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.json()["data"]["city"], "Gurugram")

        # 3. Update Location
        update_payload = {
            "name": "Test Cyber Hub Tech Park",
            "city": "Gurugram Sector 24"
        }
        put_res = self.client.put(f"/api/v1/payroll/masters/locations/{loc_id}", json=update_payload, headers=headers)
        self.assertEqual(put_res.status_code, 200)
        self.assertEqual(put_res.json()["data"]["name"], "Test Cyber Hub Tech Park")
        self.assertEqual(put_res.json()["data"]["city"], "Gurugram Sector 24")

        # 4. List Locations
        list_res = self.client.get("/api/v1/payroll/masters/locations", headers=headers)
        self.assertEqual(list_res.status_code, 200)
        locs = list_res.json()["data"]
        found = any(l["id"] == loc_id for l in locs)
        self.assertTrue(found)

        # 5. Delete Location
        del_res = self.client.delete(f"/api/v1/payroll/masters/locations/{loc_id}", headers=headers)
        self.assertEqual(del_res.status_code, 200)
        self.created_location_ids.remove(loc_id)

    def test_02_salary_template_structured_and_non_structured(self):
        """Test salary template creation with structured vs non-structured models."""
        headers = {"X-Tenant-ID": str(self.tenant.id)}

        # Structured Model Template
        structured_payload = {
            "name": "Test Structured Engineer CTC",
            "code": "TEST-ENG-STR",
            "compensation_model": "STRUCTURED_SALARY",
            "basic_percentage": 50.0,
            "hra_percentage": 20.0,
            "da_percentage": 10.0,
            "conveyance_fixed": 1600.0,
            "medical_fixed": 1250.0,
            "enable_pf": True,
            "enable_esi": True,
            "enable_pt": True,
            "is_active": True
        }
        res1 = self.client.post("/api/v1/payroll/masters/templates", json=structured_payload, headers=headers)
        self.assertEqual(res1.status_code, 200, res1.text)
        t1_id = res1.json()["data"]["id"]
        self.created_template_ids.append(t1_id)
        self.assertEqual(res1.json()["data"]["compensation_model"], "STRUCTURED_SALARY")
        self.assertEqual(res1.json()["data"]["basic_percentage"], 50.0)

        # Non-Structured Model Template (e.g. MONTHLY_FIXED with 0 breakdown)
        fixed_payload = {
            "name": "Test Monthly Fixed Base Template",
            "code": "TEST-FIXED-BASE",
            "compensation_model": "MONTHLY_FIXED",
            "basic_percentage": 0.0,
            "hra_percentage": 0.0,
            "da_percentage": 0.0,
            "conveyance_fixed": 0.0,
            "medical_fixed": 0.0,
            "enable_pf": False,
            "enable_esi": False,
            "enable_pt": True,
            "is_active": True
        }
        res2 = self.client.post("/api/v1/payroll/masters/templates", json=fixed_payload, headers=headers)
        self.assertEqual(res2.status_code, 200, res2.text)
        t2_id = res2.json()["data"]["id"]
        self.created_template_ids.append(t2_id)
        self.assertEqual(res2.json()["data"]["compensation_model"], "MONTHLY_FIXED")

    def test_03_payroll_html_and_dashboard_js_content_hygiene(self):
        """Verify payroll.html and dashboard.js contain required UI refinements."""
        with open("src/server/templates/payroll.html", "r", encoding="utf-8") as f:
            payroll_html = f.read()

        # 1. Section Header: Monthly Payroll
        self.assertIn("Monthly Payroll", payroll_html)
        self.assertNotIn("Monthly Payroll Batches Lifecycle", payroll_html)

        # 2. Location Modal presence
        self.assertIn('id="locationModal"', payroll_html)
        self.assertIn('id="locModalName"', payroll_html)
        self.assertIn('id="locModalCode"', payroll_html)
        self.assertIn('id="locModalCity"', payroll_html)
        self.assertIn('id="locModalState"', payroll_html)
        self.assertIn('id="locModalContact"', payroll_html)
        self.assertIn('id="locModalAddress"', payroll_html)
        self.assertIn('id="btnSaveLocation"', payroll_html)

        # 3. Conditional breakdown section
        self.assertIn('id="tplComponentBreakdownSection"', payroll_html)
        self.assertIn('toggleTemplateComponentVisibility()', payroll_html)

        # 4. Status cleaned up (no Active Blueprint)
        self.assertNotIn("Active Blueprint", payroll_html)

        # 5. Check dashboard.js for formatAttendanceDateTime
        with open("src/server/static/js/dashboard.js", "r", encoding="utf-8") as f:
            dashboard_js = f.read()
        self.assertIn("formatAttendanceDateTime", dashboard_js)

if __name__ == "__main__":
    unittest.main()
