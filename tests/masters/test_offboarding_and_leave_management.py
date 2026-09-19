"""
Unit & Integration Tests for Employee Offboarding, Leave Master & Leave Quotas,
Approval Workflow, Employee Portal Self-Service, and Paid Leave Payroll Integration.
"""
import os
import sys
from datetime import datetime, time, date, timedelta
from pathlib import Path
import unittest
import numpy as np
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

from src.database.session import init_db, get_db_context, seed_default_leave_types
from src.database.models import (
    Tenant,
    User,
    Student,
    AttendanceRecord,
    SystemBranding,
    Department,
    LeaveType,
    LeaveBalance,
    LeaveRequest,
)
from src.core.attendance_manager import AttendanceManager
from src.server.app import app
from src.server.routes.api_employee_portal import create_employee_token, decode_employee_token


class TestOffboardingAndLeaveManagement(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.client = TestClient(app)
        self.clean_test_data()

    def tearDown(self):
        self.clean_test_data()

    def clean_test_data(self):
        with get_db_context() as db:
            test_rolls = ["EMP_OFFBOARD_01", "EMP_OFFBOARD_02", "EMP_LEAVE_01", "EMP_LEAVE_02"]
            st_ids = [s.id for s in db.query(Student).filter(Student.roll_number.in_(test_rolls)).all()]
            if st_ids:
                db.query(LeaveRequest).filter(LeaveRequest.student_id.in_(st_ids)).delete(synchronize_session=False)
                db.query(LeaveBalance).filter(LeaveBalance.student_id.in_(st_ids)).delete(synchronize_session=False)
                db.query(AttendanceRecord).filter(AttendanceRecord.student_id.in_(st_ids)).delete(synchronize_session=False)
                db.query(Student).filter(Student.id.in_(st_ids)).delete(synchronize_session=False)
                db.commit()

            # Clean test leave types
            test_codes = ["TEST_MAT", "TEST_PAT"]
            test_lts = db.query(LeaveType).filter(LeaveType.code.in_(test_codes)).all()
            for lt in test_lts:
                db.delete(lt)
            db.commit()

    def test_01_employee_relieve_and_reinstate_workflow(self):
        """Test relieving an active employee, verifying status transition and data preservation."""
        with get_db_context() as db:
            ssec = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            self.assertIsNotNone(ssec)
            ssec_id = str(ssec.id)

            emp = Student(
                tenant_id=ssec.id,
                roll_number="EMP_OFFBOARD_01",
                name="John Doe",
                user_role="employee",
                department="Engineering",
                is_active=True,
                employment_status="ACTIVE",
            )
            db.add(emp)
            db.commit()
            db.refresh(emp)
            emp_id = emp.id

            # Add a past attendance record to verify historical preservation
            rec = AttendanceRecord(
                tenant_id=ssec.id,
                student_id=emp_id,
                node_id="GATE-01",
                check_in_time=datetime.now() - timedelta(days=1),
                check_out_time=datetime.now() - timedelta(days=1) + timedelta(hours=8),
                work_duration_minutes=480,
                confidence_distance=0.15,
                status="PRESENT",
            )
            db.add(rec)
            db.commit()

        # Step 1: Relieve the employee via API
        relieve_res = self.client.post(
            f"/api/v1/enroll/student/{emp_id}/relieve",
            headers={"X-Tenant-ID": ssec_id},
            json={
                "relieving_reason": "Resigned for higher studies",
                "relieved_at": datetime.now().isoformat(),
            },
        )
        self.assertEqual(relieve_res.status_code, 200)
        relieve_data = relieve_res.json()
        self.assertEqual(relieve_data["status"], "success")
        self.assertEqual(relieve_data["employee"]["employment_status"], "RELIEVED")
        self.assertFalse(relieve_data["employee"]["is_active"])

        # Step 2: Verify database state & attendance history preservation
        with get_db_context() as db:
            saved_emp = db.query(Student).filter(Student.id == emp_id).first()
            self.assertIsNotNone(saved_emp)
            self.assertFalse(saved_emp.is_active)
            self.assertEqual(saved_emp.employment_status, "RELIEVED")
            self.assertEqual(saved_emp.relieving_reason, "Resigned for higher studies")

            # Check attendance records still exist
            records = db.query(AttendanceRecord).filter(AttendanceRecord.student_id == emp_id).all()
            self.assertEqual(len(records), 1)

        # Step 3: Test filtering on GET /students
        active_res = self.client.get("/api/v1/enroll/students?status=ACTIVE", headers={"X-Tenant-ID": ssec_id})
        self.assertEqual(active_res.status_code, 200)
        active_ids = [s["id"] for s in active_res.json()["students"]]
        self.assertNotIn(emp_id, active_ids)

        relieved_res = self.client.get("/api/v1/enroll/students?status=RELIEVED", headers={"X-Tenant-ID": ssec_id})
        self.assertEqual(relieved_res.status_code, 200)
        relieved_ids = [s["id"] for s in relieved_res.json()["students"]]
        self.assertIn(emp_id, relieved_ids)

        # Step 4: Reinstate the employee
        reinstate_res = self.client.post(
            f"/api/v1/enroll/student/{emp_id}/reinstate",
            headers={"X-Tenant-ID": ssec_id},
            json={},
        )
        self.assertEqual(reinstate_res.status_code, 200)
        reinstate_data = reinstate_res.json()
        self.assertEqual(reinstate_data["employee"]["employment_status"], "ACTIVE")
        self.assertTrue(reinstate_data["employee"]["is_active"])

    def test_02_relieved_employee_attendance_punch_blocking(self):
        """Verify that AttendanceManager rejects and blocks punches for relieved employees."""
        with get_db_context() as db:
            ssec = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            ssec_id = ssec.id

            emp = Student(
                tenant_id=ssec_id,
                roll_number="EMP_OFFBOARD_02",
                name="Inactive Worker",
                user_role="employee",
                is_active=False,
                employment_status="RELIEVED",
            )
            db.add(emp)
            db.commit()
            db.refresh(emp)
            emp_id = emp.id

        # Attempt to mark attendance
        manager = AttendanceManager()
        result = manager.mark_attendance(
            student_id=emp_id,
            node_id="GATE-01",
            confidence_distance=0.15,
            tenant_id=ssec_id,
        )

        self.assertFalse(result["attendance_logged"])
        self.assertTrue(result.get("is_relieved", False))
        self.assertEqual(result.get("status"), "BLOCKED")
        self.assertIn("relieved", result.get("message", "").lower())

        # Verify no attendance record was created
        with get_db_context() as db:
            count = db.query(AttendanceRecord).filter(AttendanceRecord.student_id == emp_id).count()
            self.assertEqual(count, 0)

    def test_03_leave_master_crud_and_balance_initialization(self):
        """Verify creation of leave types and standard quota balance initialization."""
        with get_db_context() as db:
            ssec = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            ssec_id = str(ssec.id)

        # Create custom leave type
        payload = {
            "name": "Maternity / Parental Leave",
            "code": "TEST_MAT",
            "description": "Parental leave policy",
            "is_paid": True,
            "default_days_per_year": 30.0,
            "is_active": True,
        }

        create_res = self.client.post("/api/v1/leave/types", headers={"X-Tenant-ID": ssec_id}, json=payload)
        self.assertEqual(create_res.status_code, 200)
        res_data = create_res.json()
        self.assertEqual(res_data["status"], "success")

        # Fetch list and verify created type
        list_res = self.client.get("/api/v1/leave/types", headers={"X-Tenant-ID": ssec_id})
        self.assertEqual(list_res.status_code, 200)
        types = list_res.json()["leave_types"]
        mat_type = next((t for t in types if t["code"] == "TEST_MAT"), None)
        self.assertIsNotNone(mat_type)
        self.assertEqual(mat_type["default_days_per_year"], 30.0)

        # Test balance initialization
        with get_db_context() as db:
            exec_emp = Student(
                tenant_id=int(ssec_id),
                roll_number="EMP_LEAVE_01",
                name="Executive Officer",
                is_active=True,
            )
            db.add(exec_emp)
            db.commit()
            db.refresh(exec_emp)
            exec_id = exec_emp.id

        # Query balance for employee
        bal_res = self.client.get(f"/api/v1/leave/balances/{exec_id}", headers={"X-Tenant-ID": ssec_id})
        self.assertEqual(bal_res.status_code, 200)
        balances = bal_res.json()["balances"]
        mat_bal = next((b for b in balances if b["leave_type_code"] == "TEST_MAT"), None)
        self.assertIsNotNone(mat_bal)
        self.assertEqual(mat_bal["total_allocated"], 30.0)
        self.assertEqual(mat_bal["remaining_days"], 30.0)

    def test_04_employee_portal_leave_application_and_cancellation(self):
        """Verify employee self-service leave application, balance hold, and pre-approval cancellation."""
        with get_db_context() as db:
            ssec = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            ssec_id = ssec.id

            seed_default_leave_types(db, ssec_id)
            db.commit()

            cl_type = db.query(LeaveType).filter(LeaveType.tenant_id == ssec_id, LeaveType.code == "CL").first()
            self.assertIsNotNone(cl_type)
            cl_id = cl_type.id

            emp = Student(
                tenant_id=ssec_id,
                roll_number="EMP_LEAVE_02",
                name="Bob Developer",
                is_active=True,
                employment_status="ACTIVE",
            )
            db.add(emp)
            db.commit()
            db.refresh(emp)
            emp_id = emp.id

        # Create employee portal JWT token
        token = create_employee_token(student_id=emp_id, tenant_id=ssec_id, roll_number="EMP_LEAVE_02", name="Bob Developer")
        auth_headers = {"Authorization": f"Bearer {token}"}

        # Step 1: Check initial balances via portal API
        bal_res = self.client.get("/api/v1/employee/leave/balances", headers=auth_headers)
        self.assertEqual(bal_res.status_code, 200)
        balances = bal_res.json()["balances"]
        cl_bal = next((b for b in balances if b["leave_type_code"] == "CL"), None)
        self.assertIsNotNone(cl_bal)
        self.assertEqual(cl_bal["remaining_days"], 12.0)
        self.assertEqual(cl_bal["pending_days"], 0.0)

        # Step 2: Apply for 2 days leave
        apply_payload = {
            "leave_type_id": cl_id,
            "start_date": (date.today() + timedelta(days=5)).isoformat(),
            "end_date": (date.today() + timedelta(days=6)).isoformat(),
            "is_half_day": False,
            "reason": "Family function",
        }
        apply_res = self.client.post("/api/v1/employee/leave/apply", headers=auth_headers, json=apply_payload)
        self.assertEqual(apply_res.status_code, 200)
        req_data = apply_res.json()
        req_id = req_data["request"]["id"]
        self.assertEqual(req_data["status"], "success")

        # Step 3: Verify balance now has 2 pending days and 10 remaining days
        bal_res2 = self.client.get("/api/v1/employee/leave/balances", headers=auth_headers)
        cl_bal2 = next((b for b in bal_res2.json()["balances"] if b["leave_type_code"] == "CL"), None)
        self.assertEqual(cl_bal2["pending_days"], 2.0)
        self.assertEqual(cl_bal2["remaining_days"], 10.0)

        # Step 4: Employee cancels application before admin review
        cancel_res = self.client.post(f"/api/v1/employee/leave/requests/{req_id}/cancel", headers=auth_headers)
        self.assertEqual(cancel_res.status_code, 200)
        self.assertEqual(cancel_res.json()["status"], "success")

        # Step 5: Verify pending days released back to remaining days
        bal_res3 = self.client.get("/api/v1/employee/leave/balances", headers=auth_headers)
        cl_bal3 = next((b for b in bal_res3.json()["balances"] if b["leave_type_code"] == "CL"), None)
        self.assertEqual(cl_bal3["pending_days"], 0.0)
        self.assertEqual(cl_bal3["remaining_days"], 12.0)

    def test_05_admin_leave_approval_and_payroll_wage_credit(self):
        """Verify admin leave approval and automatic 8.0 hrs paid leave wage credit in payroll."""
        with get_db_context() as db:
            ssec = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            if ssec:
                ssec.subscription_plan = "PRO"
                db.commit()
            ssec_id = str(ssec.id)

            seed_default_leave_types(db, int(ssec_id))
            db.commit()

            cl_type = db.query(LeaveType).filter(LeaveType.tenant_id == int(ssec_id), LeaveType.code == "CL").first()
            cl_id = cl_type.id

            emp = Student(
                tenant_id=int(ssec_id),
                roll_number="EMP_LEAVE_01",
                name="Alice Engineer",
                hourly_rate=20.0,
                is_active=True,
                employment_status="ACTIVE",
            )
            db.add(emp)
            db.commit()
            db.refresh(emp)
            emp_id = emp.id

        token = create_employee_token(student_id=emp_id, tenant_id=int(ssec_id), roll_number="EMP_LEAVE_01", name="Alice Engineer")
        auth_headers = {"Authorization": f"Bearer {token}"}

        # Step 1: Apply for 1 day leave in current month
        target_leave_date = date.today().replace(day=10)
        apply_payload = {
            "leave_type_id": cl_id,
            "start_date": target_leave_date.isoformat(),
            "end_date": target_leave_date.isoformat(),
            "is_half_day": False,
            "reason": "Personal work",
        }
        apply_res = self.client.post("/api/v1/employee/leave/apply", headers=auth_headers, json=apply_payload)
        self.assertEqual(apply_res.status_code, 200)
        req_id = apply_res.json()["request"]["id"]

        # Step 2: Admin approves the leave request
        review_res = self.client.post(
            f"/api/v1/leave/requests/{req_id}/review",
            headers={"X-Tenant-ID": ssec_id},
            json={"status": "APPROVED", "admin_remarks": "Approved by HR"},
        )
        self.assertEqual(review_res.status_code, 200)
        self.assertEqual(review_res.json()["status"], "success")

        # Step 3: Check LeaveBalance used_days updated
        with get_db_context() as db:
            bal = db.query(LeaveBalance).filter(LeaveBalance.student_id == emp_id, LeaveBalance.leave_type_id == cl_id).first()
            self.assertEqual(bal.used_days, 1.0)
            self.assertEqual(bal.pending_days, 0.0)
            self.assertEqual(bal.remaining_days, 11.0)

        # Step 4: Verify Payroll calculation includes 8.0 hrs paid leave credit
        first_day = target_leave_date.replace(day=1)
        last_day = (first_day + timedelta(days=32)).replace(day=1) - timedelta(days=1)

        payroll_res = self.client.get(
            f"/api/v1/payroll/summary?start_date={first_day.isoformat()}&end_date={last_day.isoformat()}",
            headers={"X-Tenant-ID": ssec_id},
        )
        self.assertEqual(payroll_res.status_code, 200)
        p_data = payroll_res.json()
        emp_pay = next((e for e in p_data["items"] if e["student_id"] == emp_id), None)
        self.assertIsNotNone(emp_pay)
        # Paid leave hours should be 8.0
        self.assertEqual(emp_pay["paid_leave_hours"], 8.0)
        self.assertEqual(emp_pay["paid_leave_days"], 1.0)
        # Gross pay should be 8.0 hrs * $20.0/hr = $160.0
        self.assertEqual(emp_pay["gross_pay"], 160.0)


if __name__ == "__main__":
    unittest.main()
