import unittest
from datetime import date, datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database.models import (
    Base,
    Tenant,
    Student,
    AttendanceRecord,
    SystemBranding,
    Department,
    User,
    LeaveType,
    LeaveRequest,
    CompanyLocation,
    DesignationMaster,
    SalaryComponent,
    SalaryTemplate,
    EmployeeSalaryStructure,
    SalaryRevisionHistory,
    PayrollBatch,
    PayrollPayslip,
)
from src.database.session import get_db, seed_default_salary_components, seed_default_salary_templates, seed_default_locations_and_designations
from src.core.payroll_engine import (
    number_to_words_inr,
    calculate_employee_payroll,
    get_effective_salary_structures,
)
from src.server.app import app
from src.server.tenant_middleware import get_current_tenant
from src.server.rbac_middleware import get_current_user

# In-memory SQLite with StaticPool so all threads/requests share the exact same DB
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


class TestIndianPayrollSystem(unittest.TestCase):

    def setUp(self):
        Base.metadata.create_all(bind=test_engine)
        self.db = TestingSessionLocal()

        # Create Tenant
        self.tenant = Tenant(
            name="Apex Tech India Pvt Ltd",
            slug="apex-tech-test",
            tenant_type="corporate",
            subscription_plan="PRO",
            is_active=True,
        )
        self.db.add(self.tenant)
        self.db.flush()

        # Branding & Statutory Defaults
        self.branding = SystemBranding(
            tenant_id=self.tenant.id,
            institution_name="Apex Tech India",
            short_code="APEX",
            currency_symbol="₹",
            payroll_structure="STRUCTURED_SALARY",
            default_hourly_rate=200.0,
            standard_working_hours_per_day=8.0,
            enable_overtime=True,
            overtime_rate_multiplier=1.5,
            holiday_ot_multiplier=2.0,
            epf_employee_pct=12.0,
            epf_employer_pct=12.0,
            epf_ceiling_limit=15000.0,
            enable_pf_ceiling=True,
            esic_employee_pct=0.75,
            esic_employer_pct=3.25,
            esi_gross_threshold=21000.0,
            pt_monthly_default=200.0,
        )
        self.db.add(self.branding)

        # Admin User
        self.admin_user = User(
            tenant_id=self.tenant.id,
            username="apex_admin",
            email="admin@apextech.in",
            role="TENANT_ADMIN",
            full_name="Apex Admin",
            password_hash="test_hash",
            is_active=True,
        )
        self.db.add(self.admin_user)

        # Department
        self.dept = Department(
            tenant_id=self.tenant.id,
            name="Engineering",
            code="ENG",
        )
        self.db.add(self.dept)
        self.db.flush()

        # Seed Defaults
        seed_default_salary_components(self.db, self.tenant.id)
        seed_default_salary_templates(self.db, self.tenant.id)
        seed_default_locations_and_designations(self.db, self.tenant.id)
        self.db.commit()

        # Override dependencies in FastAPI TestClient
        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        def override_get_current_tenant():
            return self.tenant

        def override_get_current_user():
            return self.admin_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_tenant] = override_get_current_tenant
        app.dependency_overrides[get_current_user] = override_get_current_user

        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(bind=test_engine)

    # ----------------------------------------------------------------------
    # 1. Test Number to Words INR Formatter
    # ----------------------------------------------------------------------
    def test_number_to_words_inr(self):
        self.assertEqual(number_to_words_inr(0), "Rupees Zero Only")
        self.assertEqual(number_to_words_inr(500), "Rupees Five Hundred Only")
        self.assertEqual(number_to_words_inr(15000), "Rupees Fifteen Thousand Only")
        self.assertEqual(number_to_words_inr(45250), "Rupees Forty-Five Thousand Two Hundred and Fifty Only")
        self.assertEqual(number_to_words_inr(125000.50), "Rupees One Lakh Twenty-Five Thousand and Fifty Paise Only")
        self.assertEqual(number_to_words_inr(15000000), "Rupees One Crore Fifty Lakh Only")

    # ----------------------------------------------------------------------
    # 2. Test Multi-Model Compensation Engine & Statutory Liabilities
    # ----------------------------------------------------------------------
    def test_structured_salary_calculation_with_pf_ceiling_and_pt(self):
        # Create Employee with ₹50,000 monthly gross structure
        emp = Student(
            tenant_id=self.tenant.id,
            roll_number="APEX-EMP-001",
            name="Aarav Sharma",
            department_id=self.dept.id,
            user_role="employee",
            pan_number="ABCDE1234F",
            uan_number="100123456789",
            bank_name="HDFC Bank",
            bank_account_number="50100123456789",
            bank_ifsc_code="HDFC0001234",
            is_active=True,
        )
        self.db.add(emp)
        self.db.flush()

        structure = EmployeeSalaryStructure(
            tenant_id=self.tenant.id,
            student_id=emp.id,
            compensation_model="STRUCTURED_SALARY",
            annual_ctc=600000.0,
            monthly_gross=50000.0,
            monthly_basic=25000.0,
            monthly_da=0.0,
            monthly_hra=10000.0,
            conveyance_allowance=1600.0,
            medical_allowance=1250.0,
            special_allowance=12150.0,
            enable_pf=True,
            pf_capped_at_ceiling=True,  # Capped at ₹15,000 wage -> 12% = ₹1,800
            enable_esi=True,
            enable_pt=True,
            pt_monthly_amount=200.0,
            effective_from_date=date(2026, 9, 1),
            is_current=True,
        )
        self.db.add(structure)

        # Add 26 days of attendance (Full month present)
        for d in range(1, 27):
            att_date = date(2026, 9, d)
            rec = AttendanceRecord(
                tenant_id=self.tenant.id,
                student_id=emp.id,
                timestamp=datetime.combine(att_date, datetime.min.time()) + timedelta(hours=9),
                confidence_distance=0.45,
                check_in_time=datetime.combine(att_date, datetime.min.time()) + timedelta(hours=9),
                check_out_time=datetime.combine(att_date, datetime.min.time()) + timedelta(hours=17),
                work_duration_minutes=480,
                shift_status="COMPLETED",
            )
            self.db.add(rec)
        self.db.commit()

        # Compute payroll
        res = calculate_employee_payroll(
            db=self.db,
            tenant=self.tenant,
            student=emp,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30),
            total_working_days=26.0,
        )

        self.assertEqual(res["gross_earnings"], 50000.0)
        self.assertEqual(res["basic_earned"], 25000.0)
        self.assertEqual(res["hra_earned"], 10000.0)
        # EPF should be capped at ₹15,000 ceiling * 12% = ₹1,800
        self.assertEqual(res["epf_employee"], 1800.0)
        # ESIC should be 0 because gross ₹50,000 > ₹21,000 threshold
        self.assertEqual(res["esic_employee"], 0.0)
        # Professional tax flat ₹200
        self.assertEqual(res["professional_tax"], 200.0)
        # Total Deductions = 1800 + 200 = 2000
        self.assertEqual(res["total_deductions"], 2000.0)
        # Net Salary = 50000 - 2000 = 48000
        self.assertEqual(res["net_salary"], 48000.0)
        self.assertEqual(res["breakdown"]["net_in_words"], "Rupees Forty-Eight Thousand Only")

    def test_esic_and_overtime_calculation(self):
        # Create Employee with ₹18,000 gross (Eligible for ESIC) + Overtime
        emp = Student(
            tenant_id=self.tenant.id,
            roll_number="APEX-EMP-002",
            name="Priya Patel",
            department_id=self.dept.id,
            user_role="employee",
            hourly_rate=100.0,
            monthly_base_salary=18000.0,
            is_active=True,
        )
        self.db.add(emp)
        self.db.flush()

        structure = EmployeeSalaryStructure(
            tenant_id=self.tenant.id,
            student_id=emp.id,
            compensation_model="MONTHLY_FIXED",
            annual_ctc=216000.0,
            monthly_gross=18000.0,
            monthly_basic=10800.0,
            monthly_hra=3600.0,
            special_allowance=3600.0,
            enable_pf=True,
            pf_capped_at_ceiling=True,
            enable_esi=True,
            enable_pt=True,
            pt_monthly_amount=200.0,
            effective_from_date=date(2026, 9, 1),
            is_current=True,
        )
        self.db.add(structure)

        # 26 days of attendance, including 10 hours work on weekday (2 hrs OT) and weekend work
        for d in range(1, 27):
            att_date = date(2026, 9, d)
            # 10 hours on day 1 (2 hours regular OT)
            mins = 600 if d == 1 else 480
            rec = AttendanceRecord(
                tenant_id=self.tenant.id,
                student_id=emp.id,
                timestamp=datetime.combine(att_date, datetime.min.time()) + timedelta(hours=9),
                confidence_distance=0.45,
                check_in_time=datetime.combine(att_date, datetime.min.time()) + timedelta(hours=9),
                check_out_time=datetime.combine(att_date, datetime.min.time()) + timedelta(minutes=mins),
                work_duration_minutes=mins,
                shift_status="COMPLETED",
            )
            self.db.add(rec)
        self.db.commit()

        res = calculate_employee_payroll(
            db=self.db,
            tenant=self.tenant,
            student=emp,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30),
            total_working_days=26.0,
        )

        self.assertGreater(res["gross_earnings"], 18000.0)
        # ESIC should be applied (0.75% on gross) because base monthly is <= ₹21,000
        self.assertGreater(res["esic_employee"], 0.0)
        self.assertEqual(res["professional_tax"], 200.0)

    # ----------------------------------------------------------------------
    # 3. Test Mid-Month Salary Revision Pro-Rating (Option 3A)
    # ----------------------------------------------------------------------
    def test_mid_month_salary_revision_prorating(self):
        emp = Student(
            tenant_id=self.tenant.id,
            roll_number="APEX-EMP-003",
            name="Rohan Verma",
            department_id=self.dept.id,
            user_role="employee",
            is_active=True,
        )
        self.db.add(emp)
        self.db.flush()

        # Structure 1: Sep 1 to Sep 15: ₹30,000 / mo
        st1 = EmployeeSalaryStructure(
            tenant_id=self.tenant.id,
            student_id=emp.id,
            compensation_model="STRUCTURED_SALARY",
            annual_ctc=360000.0,
            monthly_gross=30000.0,
            monthly_basic=15000.0,
            monthly_hra=6000.0,
            special_allowance=9000.0,
            enable_pf=True,
            enable_esi=False,
            enable_pt=True,
            effective_from_date=date(2026, 9, 1),
            effective_to_date=date(2026, 9, 15),
            is_current=False,
        )
        # Structure 2: Sep 16 onwards: Promoted to ₹60,000 / mo
        st2 = EmployeeSalaryStructure(
            tenant_id=self.tenant.id,
            student_id=emp.id,
            compensation_model="STRUCTURED_SALARY",
            annual_ctc=720000.0,
            monthly_gross=60000.0,
            monthly_basic=30000.0,
            monthly_hra=12000.0,
            special_allowance=18000.0,
            enable_pf=True,
            enable_esi=False,
            enable_pt=True,
            effective_from_date=date(2026, 9, 16),
            effective_to_date=None,
            is_current=True,
        )
        self.db.add(st1)
        self.db.add(st2)

        # Attendance 26 days
        for d in range(1, 27):
            att_date = date(2026, 9, d)
            rec = AttendanceRecord(
                tenant_id=self.tenant.id,
                student_id=emp.id,
                timestamp=datetime.combine(att_date, datetime.min.time()) + timedelta(hours=9),
                confidence_distance=0.45,
                check_in_time=datetime.combine(att_date, datetime.min.time()) + timedelta(hours=9),
                check_out_time=datetime.combine(att_date, datetime.min.time()) + timedelta(hours=17),
                work_duration_minutes=480,
                shift_status="COMPLETED",
            )
            self.db.add(rec)
        self.db.commit()

        # Pro-rated effective structures in month
        segments = get_effective_salary_structures(self.db, self.tenant.id, emp, date(2026, 9, 1), date(2026, 9, 30))
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0][0], date(2026, 9, 1))
        self.assertEqual(segments[0][1], date(2026, 9, 15))
        self.assertEqual(segments[1][0], date(2026, 9, 16))
        self.assertEqual(segments[1][1], date(2026, 9, 30))

        # Compute payroll across the full month
        res = calculate_employee_payroll(
            db=self.db,
            tenant=self.tenant,
            student=emp,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30),
            total_working_days=26.0,
        )

        # Expected gross is approximately half month on 30k (15k) + half month on 60k (30k) = 45k
        self.assertAlmostEqual(res["gross_earnings"], 45000.0, delta=500.0)

    # ----------------------------------------------------------------------
    # 4. Test Masters CRUD API Endpoints
    # ----------------------------------------------------------------------
    def test_organization_masters_api(self):
        # 1. Locations
        res_loc = self.client.get("/api/v1/payroll/masters/locations")
        self.assertEqual(res_loc.status_code, 200)
        self.assertTrue(len(res_loc.json()["data"]) > 0)

        res_new_loc = self.client.post("/api/v1/payroll/masters/locations", json={
            "name": "Bengaluru Innovation Hub",
            "code": "BLR1",
            "city": "Bengaluru",
            "state": "Karnataka",
        })
        self.assertEqual(res_new_loc.status_code, 200)
        loc_id = res_new_loc.json()["data"]["id"]

        # 2. Designations
        res_desig = self.client.get("/api/v1/payroll/masters/designations")
        self.assertEqual(res_desig.status_code, 200)
        self.assertTrue(len(res_desig.json()["data"]) > 0)

        # 3. Salary Templates
        res_tpl = self.client.get("/api/v1/payroll/masters/templates")
        self.assertEqual(res_tpl.status_code, 200)
        self.assertTrue(len(res_tpl.json()["data"]) >= 3)

        # 4. Salary Components
        res_comp = self.client.get("/api/v1/payroll/masters/components")
        self.assertEqual(res_comp.status_code, 200)
        self.assertTrue(len(res_comp.json()["data"]) >= 6)

    # ----------------------------------------------------------------------
    # 5. Test Payroll Batch Lifecycle & Bank Advice Export
    # ----------------------------------------------------------------------
    def test_payroll_batch_lifecycle_and_disbursement(self):
        # Create 2 employees
        for i in range(1, 3):
            emp = Student(
                tenant_id=self.tenant.id,
                roll_number=f"APEX-BATCH-{i:03d}",
                name=f"Employee {i}",
                department_id=self.dept.id,
                user_role="employee",
                monthly_base_salary=40000.0,
                bank_name="ICICI Bank",
                bank_account_number=f"00112233445{i}",
                bank_ifsc_code="ICIC0000011",
                is_active=True,
            )
            self.db.add(emp)
        self.db.commit()

        # 1. Generate Batch
        gen_res = self.client.post("/api/v1/payroll/batches/generate", json={
            "period_year": 2026,
            "period_month": 9,
            "working_days": 26.0,
        })
        self.assertEqual(gen_res.status_code, 200)
        batch_id = gen_res.json()["data"]["id"]
        self.assertEqual(gen_res.json()["data"]["status"], "DRAFT")

        # 2. Get Batch Details
        detail_res = self.client.get(f"/api/v1/payroll/batches/{batch_id}")
        self.assertEqual(detail_res.status_code, 200)
        payslips = detail_res.json()["payslips"]
        self.assertGreaterEqual(len(payslips), 2)
        payslip_id = payslips[0]["id"]

        # 3. Verify Batch
        verify_res = self.client.post(f"/api/v1/payroll/batches/{batch_id}/verify")
        self.assertEqual(verify_res.status_code, 200)
        self.assertEqual(verify_res.json()["data"]["status"], "VERIFIED")

        # 4. Approve Batch
        approve_res = self.client.post(f"/api/v1/payroll/batches/{batch_id}/approve")
        self.assertEqual(approve_res.status_code, 200)
        self.assertEqual(approve_res.json()["data"]["status"], "APPROVED")

        # 5. Disburse Batch
        disburse_res = self.client.post(f"/api/v1/payroll/batches/{batch_id}/disburse")
        self.assertEqual(disburse_res.status_code, 200)
        self.assertEqual(disburse_res.json()["data"]["status"], "DISBURSED")

        # 6. Export Bank Advice
        bank_res = self.client.get(f"/api/v1/payroll/batches/{batch_id}/export-bank-advice?export_format=csv")
        self.assertEqual(bank_res.status_code, 200)
        self.assertIn("Beneficiary Name", bank_res.text)
        self.assertIn("Account Number", bank_res.text)

        # 7. Get Individual Payslip Details & Printable HTML view
        ps_res = self.client.get(f"/api/v1/payroll/payslips/{payslip_id}")
        self.assertEqual(ps_res.status_code, 200)
        self.assertIn("net_in_words", ps_res.json()["data"])

        html_res = self.client.get(f"/payroll/payslip/{payslip_id}")
        self.assertEqual(html_res.status_code, 200)
        self.assertIn("SALARY SLIP", html_res.text.upper())
        self.assertIn("₹", html_res.text)


if __name__ == "__main__":
    unittest.main()
