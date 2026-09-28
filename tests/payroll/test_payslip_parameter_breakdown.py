import unittest
import json
from datetime import date, datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database.models import (
    Base,
    Tenant,
    Student,
    User,
    PayrollBatch,
    PayrollPayslip,
    EmployeeSalaryStructure,
    SalaryTemplate,
    SystemBranding,
    Department,
)
from src.database.session import get_db
from src.server.app import app
from src.server.tenant_middleware import get_current_tenant
from src.server.rbac_middleware import get_current_user
from src.core.payroll_engine import calculate_employee_payroll


class TestPayslipParameterBreakdown(unittest.TestCase):

    def setUp(self):
        self.test_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.test_engine)
        Base.metadata.create_all(bind=self.test_engine)
        self.db = self.TestingSessionLocal()

        self.tenant = Tenant(
            name="Transparency Test Corp",
            slug="transparency-corp-test",
            tenant_type="corporate",
            subscription_plan="PRO",
            is_active=True,
        )
        self.db.add(self.tenant)
        self.db.flush()

        self.admin_user = User(
            tenant_id=self.tenant.id,
            username="admin_transparency",
            email="admin@transparency.com",
            role="TENANT_ADMIN",
            full_name="Admin Transparency",
            password_hash="testpass",
            is_active=True,
        )
        self.db.add(self.admin_user)

        self.branding = SystemBranding(
            tenant_id=self.tenant.id,
            institution_name="Transparency Test Corp",
            short_code="TTC",
            currency_symbol="₹",
            payroll_structure="STRUCTURED_SALARY",
        )
        self.db.add(self.branding)

        self.dept = Department(
            tenant_id=self.tenant.id,
            name="Finance",
            code="FIN",
        )
        self.db.add(self.dept)
        self.db.commit()

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
        Base.metadata.drop_all(bind=self.test_engine)

    def test_payslip_parameter_breakdown_rendering(self):
        # 1. Create employee
        employee = Student(
            tenant_id=self.tenant.id,
            name="Rohit Sharma",
            roll_number="EMP-ROHIT-01",
            user_role="employee",
            department="Finance",
            monthly_base_salary=35000.0,
            is_active=True,
        )
        self.db.add(employee)
        self.db.commit()
        self.db.refresh(employee)

        # 2. Add salary structure
        struct = EmployeeSalaryStructure(
            tenant_id=self.tenant.id,
            student_id=employee.id,
            compensation_model="STRUCTURED_SALARY",
            monthly_gross=50000.0,
            monthly_basic=25000.0,
            monthly_da=2500.0,
            monthly_hra=5000.0,
            conveyance_allowance=1600.0,
            medical_allowance=1250.0,
            special_allowance=14650.0,
            daily_rate=1923.08,
            hourly_rate=240.38,
            enable_pf=True,
            enable_esi=False,
            enable_pt=True,
            effective_from_date=date(2026, 9, 1),
            is_current=True,
        )
        self.db.add(struct)
        self.db.commit()

        # 3. Create batch & payslip
        batch = PayrollBatch(
            tenant_id=self.tenant.id,
            batch_number="BATCH-TEST-202609",
            period_month=9,
            period_year=2026,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30),
            total_working_days=26.0,
            status="DRAFT",
            total_employees_count=1,
        )
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)

        breakdown_payload = {
            "parameters": {
                "compensation_model": "STRUCTURED_SALARY",
                "monthly_basic": 25000.0,
                "da_percentage": 10.0,
                "hra_percentage": 20.0,
                "monthly_da": 2500.0,
                "monthly_hra": 5000.0,
                "daily_salary_rate": 1923.08,
                "hourly_rate": 240.38,
                "monthly_gross": 50000.0,
                "fixed_allowances": 17500.0,
                "is_pf_eligible": True,
                "is_esi_eligible": False,
                "is_pt_eligible": True,
                "is_tds_applicable": False,
            }
        }

        payslip = PayrollPayslip(
            tenant_id=self.tenant.id,
            batch_id=batch.id,
            student_id=employee.id,
            period_month=9,
            period_year=2026,
            calendar_days=30,
            working_days=26.0,
            present_days=26.0,
            basic_earned=25000.0,
            da_earned=2500.0,
            hra_earned=5000.0,
            gross_earnings=50000.0,
            net_salary=46800.0,
            breakdown_json=json.dumps(breakdown_payload),
        )
        self.db.add(payslip)
        self.db.commit()
        self.db.refresh(payslip)

        # 4. Request the HTML payslip view
        res = self.client.get(f"/payroll/payslip/{payslip.id}")
        self.assertEqual(res.status_code, 200)
        html = res.text

        # 5. Assert transparent compensation parameters card is present
        self.assertIn("Compensation Parameters & Verification Basis", html)
        self.assertIn("Monthly Basic", html)
        self.assertIn("25,000.00", html)
        self.assertIn("Dearness Allowance (DA)", html)
        self.assertIn("10.0%", html)
        self.assertIn("House Rent Allowance (HRA)", html)
        self.assertIn("20.0%", html)
        self.assertIn("Daily Salary Rate", html)
        self.assertIn("1,923.08", html)
        self.assertIn("Hourly Pay Rate", html)
        self.assertIn("240.38", html)
        self.assertIn("Statutory Applicability", html)
        self.assertIn("PF:", html)
        self.assertIn("PT", html)

    def test_payslip_parameter_fallback_for_legacy_payslip(self):
        # Test fallback when breakdown_json does not have 'parameters'
        employee = Student(
            tenant_id=self.tenant.id,
            name="Legacy Employee",
            roll_number="EMP-LEGACY-01",
            user_role="employee",
            department="Finance",
            monthly_base_salary=28000.0,
            is_active=True,
        )
        self.db.add(employee)
        self.db.commit()
        self.db.refresh(employee)

        struct = EmployeeSalaryStructure(
            tenant_id=self.tenant.id,
            student_id=employee.id,
            compensation_model="STRUCTURED_SALARY",
            monthly_gross=35000.0,
            monthly_basic=17500.0,
            monthly_da=1750.0,
            monthly_hra=3500.0,
            daily_rate=1346.15,
            enable_pf=True,
            effective_from_date=date(2026, 8, 1),
            is_current=True,
        )
        self.db.add(struct)

        batch = PayrollBatch(
            tenant_id=self.tenant.id,
            batch_number="BATCH-LEGACY-202608",
            period_month=8,
            period_year=2026,
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 31),
            total_working_days=26.0,
            status="FINALIZED",
            total_employees_count=1,
        )
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)

        # Legacy payslip with no parameters in breakdown_json
        payslip = PayrollPayslip(
            tenant_id=self.tenant.id,
            batch_id=batch.id,
            student_id=employee.id,
            period_month=8,
            period_year=2026,
            calendar_days=31,
            working_days=26.0,
            present_days=26.0,
            basic_earned=17500.0,
            gross_earnings=35000.0,
            net_salary=32900.0,
            breakdown_json=None,
        )
        self.db.add(payslip)
        self.db.commit()
        self.db.refresh(payslip)

        res = self.client.get(f"/payroll/payslip/{payslip.id}")
        self.assertEqual(res.status_code, 200)
        html = res.text

        # Verify fallback populated the parameters
        self.assertIn("Compensation Parameters & Verification Basis", html)
        self.assertIn("Monthly Basic", html)
        self.assertIn("17,500.00", html)

    def test_hourly_payslip_parameter_displays_na(self):
        # Test that hourly payslip displays NA for non-applicable fields
        hourly_emp = Student(
            tenant_id=self.tenant.id,
            name="Hourly Staff",
            roll_number="EMP-HOURLY-01",
            user_role="employee",
            department="Operations",
            hourly_rate=250.0,
            is_active=True,
        )
        self.db.add(hourly_emp)
        self.db.commit()
        self.db.refresh(hourly_emp)

        hourly_tpl = SalaryTemplate(
            tenant_id=self.tenant.id,
            name="Hourly Shift Template",
            code="HOURLY_SHIFT",
            compensation_model="HOURLY",
            is_active=True,
        )
        self.db.add(hourly_tpl)
        self.db.commit()
        self.db.refresh(hourly_tpl)

        struct = EmployeeSalaryStructure(
            tenant_id=self.tenant.id,
            student_id=hourly_emp.id,
            template_id=hourly_tpl.id,
            compensation_model="HOURLY",
            hourly_rate=250.0,
            monthly_gross=0.0,
            monthly_basic=0.0,
            daily_rate=0.0,
            enable_pf=False,
            enable_esi=False,
            enable_pt=False,
            effective_from_date=date(2026, 9, 1),
            is_current=True,
        )
        self.db.add(struct)

        batch = PayrollBatch(
            tenant_id=self.tenant.id,
            batch_number="BATCH-HOURLY-202609",
            period_month=9,
            period_year=2026,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30),
            total_working_days=26.0,
            status="FINALIZED",
            total_employees_count=1,
        )
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)

        payslip = PayrollPayslip(
            tenant_id=self.tenant.id,
            batch_id=batch.id,
            student_id=hourly_emp.id,
            template_id=hourly_tpl.id,
            period_month=9,
            period_year=2026,
            calendar_days=30,
            working_days=26.0,
            present_days=1.0,
            billable_hours=12.0,
            basic_earned=3000.0,
            gross_earnings=3000.0,
            net_salary=3000.0,
            breakdown_json=json.dumps({
                "parameters": {
                    "compensation_model": "HOURLY",
                    "template_name": "Hourly Shift Template",
                    "template_code": "HOURLY_SHIFT",
                    "monthly_basic": 0.0,
                    "monthly_da": 0.0,
                    "monthly_hra": 0.0,
                    "da_percentage": 0.0,
                    "hra_percentage": 0.0,
                    "daily_salary_rate": 0.0,
                    "hourly_rate": 250.0,
                    "monthly_gross": 0.0,
                    "conveyance_allowance": 0.0,
                    "medical_allowance": 0.0,
                    "enable_pf": False,
                    "enable_esi": False,
                    "enable_pt": False,
                }
            }),
        )
        self.db.add(payslip)
        self.db.commit()
        self.db.refresh(payslip)

        res = self.client.get(f"/payroll/payslip/{payslip.id}")
        self.assertEqual(res.status_code, 200)
        html = res.text

        # Verify structure indicates HOURLY
        self.assertIn("HOURLY", html)
        self.assertIn("250.00", html)
        self.assertIn("/hr", html)

        # Verify NA is rendered for Monthly Basic and Daily Salary Rate
        self.assertIn("NA", html)


if __name__ == "__main__":
    unittest.main()
