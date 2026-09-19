"""
Unit & Integration Tests for Corporate Payroll Engine, Overtime Multipliers,
Missed Checkout Adjustments, Department Transfer History, and Flexible Date Ranges.
"""
import os
import sys
from datetime import datetime, time, date, timedelta
from pathlib import Path
import unittest
from fastapi.testclient import TestClient

# Setup path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Ensure DLL path for Anaconda OpenSSL if needed
anaconda_bin = r"C:\ProgramData\Anaconda3\Library\bin"
if os.path.exists(anaconda_bin):
    try:
        os.add_dll_directory(anaconda_bin)
    except Exception:
        pass
    if anaconda_bin not in os.environ.get("PATH", ""):
        os.environ["PATH"] = anaconda_bin + os.pathsep + os.environ.get("PATH", "")

from src.database.session import init_db, get_db_context
from src.database.models import Tenant, User, Student, AttendanceRecord, SystemBranding, Department
from src.server.app import app


class TestCorporatePayrollAndDateRanges(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.client = TestClient(app)
        # Clean any stale test records and reset tenant branding
        with get_db_context() as db:
            test_rolls = ["EMP_PAYROLL_001", "EMP_PAYROLL_002", "EMP_PAYROLL_003"]
            st_ids = [s.id for s in db.query(Student).filter(Student.roll_number.in_(test_rolls)).all()]
            if st_ids:
                db.query(AttendanceRecord).filter(AttendanceRecord.student_id.in_(st_ids)).delete(synchronize_session=False)
                db.query(Student).filter(Student.id.in_(st_ids)).delete(synchronize_session=False)
                db.commit()

            ssec = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            if ssec:
                ssec.subscription_plan = "PRO"
                if ssec.branding:
                    ssec.branding.payroll_structure = "HOURLY"
                    ssec.branding.default_hourly_rate = 15.0
                    ssec.branding.standard_working_hours_per_day = 8.0
                    ssec.branding.enable_overtime = True
                    ssec.branding.overtime_rate_multiplier = 1.5
                    ssec.branding.missed_checkout_policy = "HALF_DAY"
                    ssec.branding.currency_symbol = "$"
                db.commit()

    def tearDown(self):
        with get_db_context() as db:
            test_rolls = ["EMP_PAYROLL_001", "EMP_PAYROLL_002", "EMP_PAYROLL_003"]
            st_ids = [s.id for s in db.query(Student).filter(Student.roll_number.in_(test_rolls)).all()]
            if st_ids:
                db.query(AttendanceRecord).filter(AttendanceRecord.student_id.in_(st_ids)).delete(synchronize_session=False)
                db.query(Student).filter(Student.id.in_(st_ids)).delete(synchronize_session=False)
                db.commit()

    def test_payroll_summary_and_overtime_calculation(self):
        """Verify wage calculations with standard shift, overtime premiums, and missed checkout policies."""
        with get_db_context() as db:
            ssec = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            self.assertIsNotNone(ssec)
            ssec_id = str(ssec.id)

            dept = db.query(Department).filter(Department.tenant_id == ssec.id).first()
            dept_id = dept.id if dept else None

            # Create employee with custom hourly rate of $25.00
            emp = Student(
                tenant_id=ssec.id,
                roll_number="EMP_PAYROLL_001",
                name="Alice Engineer",
                department_id=dept_id,
                department=dept.name if dept else "Engineering",
                user_role="employee",
                hourly_rate=25.0,
                is_active=True,
            )
            db.add(emp)
            db.commit()
            db.refresh(emp)
            emp_id = emp.id

            # Day 1: 10 hours worked (8.0 standard + 2.0 overtime @ 1.5x)
            day1_date = date.today() - timedelta(days=2)
            rec1 = AttendanceRecord(
                tenant_id=ssec.id,
                student_id=emp_id,
                node_id="GATE-01",
                timestamp=datetime.combine(day1_date, time(9, 0)),
                confidence_distance=0.0,
                check_in_time=datetime.combine(day1_date, time(9, 0)),
                check_out_time=datetime.combine(day1_date, time(19, 0)),
                work_duration_minutes=600,  # 10.0 hours
                shift_status="COMPLETED",
                status="PRESENT",
            )
            db.add(rec1)

            # Day 2: Missed checkout on past date -> policy HALF_DAY gives 4.0 hours
            day2_date = date.today() - timedelta(days=1)
            rec2 = AttendanceRecord(
                tenant_id=ssec.id,
                student_id=emp_id,
                node_id="GATE-01",
                timestamp=datetime.combine(day2_date, time(10, 0)),
                confidence_distance=0.0,
                check_in_time=datetime.combine(day2_date, time(10, 0)),
                check_out_time=None,  # Missed checkout
                shift_status="MISSED_CHECKOUT",
                status="PRESENT",
            )
            db.add(rec2)
            db.commit()

        # Call Payroll API as Tenant Admin
        client = TestClient(app, cookies={
            "active_role": "TENANT_ADMIN",
            "active_tenant_id": ssec_id,
        })

        start_str = (date.today() - timedelta(days=7)).isoformat()
        end_str = date.today().isoformat()

        res = client.get(f"/api/v1/payroll/summary?start_date={start_str}&end_date={end_str}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")

        # Find employee
        items = [i for i in data["items"] if i["student_id"] == emp_id]
        self.assertEqual(len(items), 1)
        emp_summary = items[0]

        # Day 1 (10 hrs) = 8.0 std + 2.0 ot
        # Day 2 (missed out) = 4.0 std (half-day policy)
        # Total = 12.0 std hours, 2.0 ot hours
        self.assertEqual(emp_summary["standard_hours"], 12.0)
        self.assertEqual(emp_summary["overtime_hours"], 2.0)
        self.assertEqual(emp_summary["total_active_hours"], 14.0)

        # Standard pay: 12.0 * $25 = $300.00
        # Overtime pay: 2.0 * $25 * 1.5 = $75.00
        # Gross pay: $375.00
        self.assertEqual(emp_summary["standard_pay"], 300.0)
        self.assertEqual(emp_summary["overtime_pay"], 75.0)
        self.assertEqual(emp_summary["gross_pay"], 375.0)
        self.assertEqual(emp_summary["missed_checkout_count"], 1)

    def test_payroll_rate_and_settings_endpoints(self):
        """Verify updating employee rates and tenant payroll settings."""
        with get_db_context() as db:
            ssec = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            ssec_id = str(ssec.id)

            emp = Student(
                tenant_id=ssec.id,
                roll_number="EMP_PAYROLL_002",
                name="Bob Tech",
                user_role="employee",
                hourly_rate=15.0,
                is_active=True,
            )
            db.add(emp)
            db.commit()
            db.refresh(emp)
            emp_id = emp.id

        client = TestClient(app, cookies={
            "active_role": "TENANT_ADMIN",
            "active_tenant_id": ssec_id,
        })

        # 1. Update Employee Rate
        res_rate = client.post("/api/v1/payroll/employee-rate", json={
            "student_id": emp_id,
            "hourly_rate": 32.5,
            "monthly_base_salary": 4800.0,
        })
        self.assertEqual(res_rate.status_code, 200)

        # Verify DB updated
        with get_db_context() as db:
            updated_emp = db.query(Student).filter(Student.id == emp_id).first()
            self.assertEqual(updated_emp.hourly_rate, 32.5)
            self.assertEqual(updated_emp.monthly_base_salary, 4800.0)

        # 2. Update Payroll Configuration
        res_cfg = client.post("/api/v1/payroll/settings", json={
            "payroll_structure": "HOURLY",
            "default_hourly_rate": 20.0,
            "standard_working_hours_per_day": 8.0,
            "enable_overtime": True,
            "overtime_rate_multiplier": 1.75,
            "missed_checkout_policy": "HALF_DAY",
            "currency_symbol": "$",
        })
        self.assertEqual(res_cfg.status_code, 200)
        self.assertEqual(res_cfg.json()["config"]["overtime_rate_multiplier"], 1.75)

    def test_payroll_export_xlsx_and_csv(self):
        """Verify payroll export endpoints generate valid Excel and CSV attachments."""
        with get_db_context() as db:
            ssec = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            ssec_id = str(ssec.id)

        client = TestClient(app, cookies={
            "active_role": "TENANT_ADMIN",
            "active_tenant_id": ssec_id,
        })

        # Test CSV export
        res_csv = client.get("/api/v1/payroll/export?export_format=csv")
        self.assertEqual(res_csv.status_code, 200)
        self.assertIn("text/csv", res_csv.headers["content-type"])
        self.assertIn("Gross Earnings", res_csv.text)

        # Test Excel export
        res_xlsx = client.get("/api/v1/payroll/export?export_format=xlsx")
        self.assertEqual(res_xlsx.status_code, 200)
        self.assertIn("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", res_xlsx.headers["content-type"])
        self.assertTrue(len(res_xlsx.content) > 100)

    def test_student_department_transfer_workflow(self):
        """Verify employee department transfer updates current assignment and records audit tracking."""
        with get_db_context() as db:
            ssec = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            ssec_id = str(ssec.id)

            # Ensure two departments exist
            dept1 = db.query(Department).filter(Department.tenant_id == ssec.id, Department.name == "Engineering").first()
            if not dept1:
                dept1 = Department(tenant_id=ssec.id, name="Engineering", code="ENG")
                db.add(dept1)

            dept2 = db.query(Department).filter(Department.tenant_id == ssec.id, Department.name == "Product Design").first()
            if not dept2:
                dept2 = Department(tenant_id=ssec.id, name="Product Design", code="DES")
                db.add(dept2)

            db.commit()
            db.refresh(dept1)
            db.refresh(dept2)

            old_dept_id = dept1.id
            old_dept_name = dept1.name
            target_dept_id = dept2.id
            target_dept_name = dept2.name

            emp = Student(
                tenant_id=ssec.id,
                roll_number="EMP_PAYROLL_003",
                name="Charlie Operations",
                department_id=old_dept_id,
                department=old_dept_name,
                user_role="employee",
                is_active=True,
            )
            db.add(emp)
            db.commit()
            db.refresh(emp)
            emp_id = emp.id

        client = TestClient(app, cookies={
            "active_role": "TENANT_ADMIN",
            "active_tenant_id": ssec_id,
        })

        # Transfer to target department
        res_transfer = client.post(f"/api/v1/enroll/student/{emp_id}/transfer-department", json={
            "department_id": target_dept_id,
        })
        self.assertEqual(res_transfer.status_code, 200)

        # Verify DB state
        with get_db_context() as db:
            transferred = db.query(Student).filter(Student.id == emp_id).first()
            self.assertEqual(transferred.department_id, target_dept_id)
            self.assertEqual(transferred.department, target_dept_name)
            self.assertEqual(transferred.previous_department_id, old_dept_id)
            self.assertIsNotNone(transferred.last_transferred_at)

    def test_attendance_records_date_range_filtering(self):
        """Verify GET /api/v1/attendance/records and export with start_date and end_date."""
        with get_db_context() as db:
            ssec = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            ssec_id = str(ssec.id)

        client = TestClient(app, cookies={
            "active_role": "TENANT_ADMIN",
            "active_tenant_id": ssec_id,
        })

        today = date.today().isoformat()
        week_ago = (date.today() - timedelta(days=7)).isoformat()

        # Query range
        res_records = client.get(f"/api/v1/attendance/records?start_date={week_ago}&end_date={today}")
        self.assertEqual(res_records.status_code, 200)
        self.assertTrue("records" in res_records.json())

        # Export range
        res_export = client.get(f"/api/v1/attendance/export?start_date={week_ago}&end_date={today}&export_format=csv")
        self.assertEqual(res_export.status_code, 200)
        self.assertIn("text/csv", res_export.headers["content-type"])

    def test_payroll_and_students_page_renders(self):
        """Verify HTML page templates render with proper corporate branding and controls."""
        with get_db_context() as db:
            ssec = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            ssec_id = str(ssec.id)

        client = TestClient(app, cookies={
            "active_role": "TENANT_ADMIN",
            "active_tenant_id": ssec_id,
        })

        res_payroll = client.get("/payroll")
        self.assertEqual(res_payroll.status_code, 200)
        self.assertIn("Payroll management", res_payroll.text)
        self.assertIn("payrollStartDate", res_payroll.text)

        res_students = client.get("/students")
        self.assertEqual(res_students.status_code, 200)
        self.assertIn("Employee Directory", res_students.text)
        self.assertIn("transferEmployeeModal", res_students.text)


if __name__ == "__main__":
    unittest.main()
