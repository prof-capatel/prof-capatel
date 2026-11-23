"""
Unit and Integration Tests for Financial Year Leave Management,
Carry-Forward Rollover Rules, FIFO Quota Consumption, and Tenant Admin Configuration.
"""

import os
import sys
from datetime import datetime, date, timedelta
from pathlib import Path
import unittest
from fastapi.testclient import TestClient

# Setup path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Anaconda DLL setup
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
    Student,
    LeaveType,
    LeaveBalance,
    LeaveRequest,
    User,
)
from src.server.app import app
from src.server.routes.api_employee_portal import create_employee_token
from src.utils.financial_year import (
    get_financial_year_info,
    parse_financial_year_code,
    list_tenant_financial_years,
)
from src.services.leave_service import LeaveService


class TestFinancialYearLeaveManagement(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.client = TestClient(app)

    def test_01_financial_year_boundary_calculations(self):
        """Test Indian Standard FY (Apr-Mar), Calendar Year (Jan-Dec), and Custom FY boundaries."""
        # 1. Indian Standard FY (start_month = 4)
        info_may = get_financial_year_info(date(2026, 5, 15), start_month=4)
        self.assertEqual(info_may["fy_code"], "2026-2027")
        self.assertEqual(info_may["start_year"], 2026)
        self.assertEqual(info_may["end_year"], 2027)
        self.assertEqual(info_may["start_date"], date(2026, 4, 1))
        self.assertEqual(info_may["end_date"], date(2027, 3, 31))

        info_feb = get_financial_year_info(date(2027, 2, 10), start_month=4)
        self.assertEqual(info_feb["fy_code"], "2026-2027")
        self.assertEqual(info_feb["start_year"], 2026)

        info_next_apr = get_financial_year_info(date(2027, 4, 1), start_month=4)
        self.assertEqual(info_next_apr["fy_code"], "2027-2028")
        self.assertEqual(info_next_apr["start_year"], 2027)

        # 2. Calendar Year (start_month = 1)
        info_cy = get_financial_year_info(date(2026, 8, 20), start_month=1)
        self.assertEqual(info_cy["fy_code"], "2026")
        self.assertEqual(info_cy["start_year"], 2026)
        self.assertEqual(info_cy["end_year"], 2026)
        self.assertEqual(info_cy["start_date"], date(2026, 1, 1))
        self.assertEqual(info_cy["end_date"], date(2026, 12, 31))

        # 3. Academic Year (start_month = 7, July)
        info_jul = get_financial_year_info(date(2026, 9, 1), start_month=7)
        self.assertEqual(info_jul["fy_code"], "2026-2027")
        self.assertEqual(info_jul["start_year"], 2026)

        info_jul_early = get_financial_year_info(date(2026, 3, 1), start_month=7)
        self.assertEqual(info_jul_early["fy_code"], "2025-2026")
        self.assertEqual(info_jul_early["start_year"], 2025)

        # 4. Parsing helpers
        parsed = parse_financial_year_code("2026-2027", start_month=4)
        self.assertEqual(parsed["start_year"], 2026)
        self.assertEqual(parsed["end_year"], 2027)

        # 5. List available FYs
        years = list_tenant_financial_years(start_month=4, count_past=2, count_future=1)
        self.assertGreaterEqual(len(years), 3)
        self.assertTrue(any(y["is_current"] for y in years))

    def test_02_tenant_admin_fy_settings_api(self):
        """Test updating tenant FY start month and fetching available FY options."""
        with get_db_context() as db:
            tenant = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            if not tenant:
                tenant = Tenant(slug="ssec", name="SSEC Testing", subscription_plan="PRO")
                db.add(tenant)
                db.commit()
            ssec_id = str(tenant.id)

        # 1. Fetch available financial years
        res = self.client.get("/api/v1/leave/financial-years", headers={"X-Tenant-ID": ssec_id})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("current_financial_year", data)
        self.assertIn("available_financial_years", data)

        # 2. Update FY start month to 4 (April)
        update_res = self.client.put(
            "/api/v1/leave/settings/financial-year",
            headers={"X-Tenant-ID": ssec_id},
            json={"start_month": 4},
        )
        self.assertEqual(update_res.status_code, 200)
        u_data = update_res.json()
        self.assertEqual(u_data["financial_year_start_month"], 4)

    def test_03_leave_type_carry_forward_crud(self):
        """Test configuring carry-forward rules (allowed, max days cap, unlimited) in Leave Master."""
        with get_db_context() as db:
            tenant = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            ssec_id = str(tenant.id)

        # Create/Update Earned Leave with carry-forward cap of 10 days
        el_payload = {
            "name": "Earned Leave FY Test",
            "code": "EL_FY_TEST",
            "is_paid": True,
            "default_days_per_year": 15.0,
            "allow_carry_forward": True,
            "max_carry_forward_days": 10.0,
            "lapse_policy": "LAPSE_EXCESS",
            "is_active": True,
        }
        res_el = self.client.post("/api/v1/leave/types", headers={"X-Tenant-ID": ssec_id}, json=el_payload)
        self.assertEqual(res_el.status_code, 200)
        el_data = res_el.json()["leave_type"]
        self.assertTrue(el_data["allow_carry_forward"])
        self.assertEqual(el_data["max_carry_forward_days"], 10.0)

        # Create Casual Leave with NO carry-forward (lapses at year end)
        cl_payload = {
            "name": "Casual Leave FY Test",
            "code": "CL_FY_TEST",
            "is_paid": True,
            "default_days_per_year": 12.0,
            "allow_carry_forward": False,
            "max_carry_forward_days": 0.0,
            "lapse_policy": "LAPSE_ALL",
            "is_active": True,
        }
        res_cl = self.client.post("/api/v1/leave/types", headers={"X-Tenant-ID": ssec_id}, json=cl_payload)
        self.assertEqual(res_cl.status_code, 200)
        cl_data = res_cl.json()["leave_type"]
        self.assertFalse(cl_data["allow_carry_forward"])

        # Create Sick Leave with UNLIMITED carry-forward (max_carry_forward_days = 0)
        sl_payload = {
            "name": "Sick Leave FY Test",
            "code": "SL_FY_TEST",
            "is_paid": True,
            "default_days_per_year": 10.0,
            "allow_carry_forward": True,
            "max_carry_forward_days": 0.0,
            "lapse_policy": "LAPSE_EXCESS",
            "is_active": True,
        }
        res_sl = self.client.post("/api/v1/leave/types", headers={"X-Tenant-ID": ssec_id}, json=sl_payload)
        self.assertEqual(res_sl.status_code, 200)
        sl_data = res_sl.json()["leave_type"]
        self.assertTrue(sl_data["allow_carry_forward"])
        self.assertEqual(sl_data["max_carry_forward_days"], 0.0)

    def test_04_carry_forward_rollover_and_lapse_calculation(self):
        """
        Verify that transitioning to a new FY rolls over unutilized days up to max cap,
        lapses excess unutilized leaves, and respects no carry-forward.
        """
        with get_db_context() as db:
            tenant = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            ssec_id = tenant.id

            el_type = db.query(LeaveType).filter(LeaveType.tenant_id == ssec_id, LeaveType.code == "EL_FY_TEST").first()
            cl_type = db.query(LeaveType).filter(LeaveType.tenant_id == ssec_id, LeaveType.code == "CL_FY_TEST").first()
            sl_type = db.query(LeaveType).filter(LeaveType.tenant_id == ssec_id, LeaveType.code == "SL_FY_TEST").first()

            # Create a test employee
            student = Student(
                tenant_id=ssec_id,
                roll_number="FY_TEST_EMP_01",
                name="David Rollover",
                hourly_rate=25.0,
                is_active=True,
                employment_status="ACTIVE",
            )
            db.add(student)
            db.commit()
            db.refresh(student)
            student_id = student.id

            # Seed Previous FY (2025-2026, start year 2025) Balances:
            # 1. EL: Allocated 15.0, Used 3.0 -> Remaining 12.0 (Cap is 10.0, so 10 carry forward, 2 lapse)
            prev_el = LeaveBalance(
                tenant_id=ssec_id,
                student_id=student_id,
                leave_type_id=el_type.id,
                year=2025,
                financial_year="2025-2026",
                annual_quota=15.0,
                total_allocated=15.0,
                used_days=3.0,
                pending_days=0.0,
                remaining_days=12.0,
            )
            # 2. CL: Allocated 12.0, Used 4.0 -> Remaining 8.0 (No CF, so 0 carry forward, 8 lapse)
            prev_cl = LeaveBalance(
                tenant_id=ssec_id,
                student_id=student_id,
                leave_type_id=cl_type.id,
                year=2025,
                financial_year="2025-2026",
                annual_quota=12.0,
                total_allocated=12.0,
                used_days=4.0,
                pending_days=0.0,
                remaining_days=8.0,
            )
            # 3. SL: Allocated 10.0, Used 2.0 -> Remaining 8.0 (Unlimited CF, so 8 carry forward, 0 lapse)
            prev_sl = LeaveBalance(
                tenant_id=ssec_id,
                student_id=student_id,
                leave_type_id=sl_type.id,
                year=2025,
                financial_year="2025-2026",
                annual_quota=10.0,
                total_allocated=10.0,
                used_days=2.0,
                pending_days=0.0,
                remaining_days=8.0,
            )
            db.add_all([prev_el, prev_cl, prev_sl])
            db.commit()

            service = LeaveService(db)

            # Initialize New FY 2026-2027 (start year 2026) for EL
            new_el = service.get_or_create_leave_balance(
                ssec_id, student, el_type, year=2026, financial_year="2026-2027"
            )
            self.assertEqual(new_el.annual_quota, 15.0)
            self.assertEqual(new_el.carried_forward_days, 10.0)  # Capped at 10.0
            self.assertEqual(new_el.lapsed_days, 2.0)            # 12.0 - 10.0 = 2.0 lapsed
            self.assertEqual(new_el.total_allocated, 25.0)       # 15.0 quota + 10.0 CF
            self.assertEqual(new_el.remaining_days, 25.0)

            # Initialize New FY 2026-2027 for CL (No Carry Forward)
            new_cl = service.get_or_create_leave_balance(
                ssec_id, student, cl_type, year=2026, financial_year="2026-2027"
            )
            self.assertEqual(new_cl.annual_quota, 12.0)
            self.assertEqual(new_cl.carried_forward_days, 0.0)   # No carry forward
            self.assertEqual(new_cl.lapsed_days, 8.0)            # All 8 unutilized days lapsed
            self.assertEqual(new_cl.total_allocated, 12.0)
            self.assertEqual(new_cl.remaining_days, 12.0)

            # Initialize New FY 2026-2027 for SL (Unlimited Carry Forward)
            new_sl = service.get_or_create_leave_balance(
                ssec_id, student, sl_type, year=2026, financial_year="2026-2027"
            )
            self.assertEqual(new_sl.annual_quota, 10.0)
            self.assertEqual(new_sl.carried_forward_days, 8.0)   # All 8 days rolled over
            self.assertEqual(new_sl.lapsed_days, 0.0)
            self.assertEqual(new_sl.total_allocated, 18.0)       # 10.0 quota + 8.0 CF
            self.assertEqual(new_sl.remaining_days, 18.0)

            db.commit()

    def test_05_fifo_leave_consumption(self):
        """
        Verify FIFO leave consumption: Carried-forward days are consumed first
        before deducting from the newly allocated annual quota.
        """
        with get_db_context() as db:
            tenant = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            ssec_id = tenant.id
            student = db.query(Student).filter(Student.roll_number == "FY_TEST_EMP_01").first()
            el_type = db.query(LeaveType).filter(LeaveType.tenant_id == ssec_id, LeaveType.code == "EL_FY_TEST").first()

            # Balance in FY 2026-2027 has: Total=25.0, Quota=15.0, CarriedForward=10.0, Used=0.0
            bal = db.query(LeaveBalance).filter(
                LeaveBalance.student_id == student.id,
                LeaveBalance.leave_type_id == el_type.id,
                LeaveBalance.year == 2026,
            ).first()
            self.assertIsNotNone(bal)
            self.assertEqual(bal.carried_forward_days, 10.0)
            self.assertEqual(bal.carried_forward_used, 0.0)

            student_id = student.id
            el_type_id = el_type.id

        token = create_employee_token(student_id=student_id, tenant_id=ssec_id, roll_number="FY_TEST_EMP_01", name="David Rollover")
        auth_headers = {"Authorization": f"Bearer {token}"}

        # Step 1: Employee applies for 6.0 days of EL in FY 2026-2027
        res1 = self.client.post(
            "/api/v1/employee/leave/apply",
            headers=auth_headers,
            json={
                "leave_type_id": el_type_id,
                "start_date": "2026-06-01",
                "end_date": "2026-06-06",
                "is_half_day": False,
                "reason": "Family vacation in summer",
            },
        )
        self.assertEqual(res1.status_code, 200)
        req1_id = res1.json()["request"]["id"]

        # Admin approves the 6-day request
        rev1 = self.client.post(
            f"/api/v1/leave/requests/{req1_id}/review",
            headers={"X-Tenant-ID": str(ssec_id)},
            json={"status": "APPROVED", "admin_remarks": "Approved 6d"},
        )
        self.assertEqual(rev1.status_code, 200)

        with get_db_context() as db:
            bal1 = db.query(LeaveBalance).filter(
                LeaveBalance.student_id == student_id,
                LeaveBalance.leave_type_id == el_type_id,
                LeaveBalance.year == 2026,
            ).first()
            # FIFO: 6 days consumed entirely from 10 days of Carried-Forward quota
            self.assertEqual(bal1.carried_forward_used, 6.0)
            self.assertEqual(bal1.used_days, 6.0)
            self.assertEqual(bal1.remaining_days, 19.0)  # 25.0 - 6.0 = 19.0 (4.0 CF + 15.0 Quota)

        # Step 2: Employee applies for another 7.0 days of EL
        res2 = self.client.post(
            "/api/v1/employee/leave/apply",
            headers=auth_headers,
            json={
                "leave_type_id": el_type_id,
                "start_date": "2026-09-10",
                "end_date": "2026-09-16",
                "is_half_day": False,
                "reason": "Autumn break",
            },
        )
        self.assertEqual(res2.status_code, 200)
        req2_id = res2.json()["request"]["id"]

        # Admin approves the 7-day request
        rev2 = self.client.post(
            f"/api/v1/leave/requests/{req2_id}/review",
            headers={"X-Tenant-ID": str(ssec_id)},
            json={"status": "APPROVED", "admin_remarks": "Approved 7d"},
        )
        self.assertEqual(rev2.status_code, 200)

        with get_db_context() as db:
            bal2 = db.query(LeaveBalance).filter(
                LeaveBalance.student_id == student_id,
                LeaveBalance.leave_type_id == el_type_id,
                LeaveBalance.year == 2026,
            ).first()
            # FIFO: Remaining 4 days of CF consumed (carried_forward_used = 10.0),
            # and remaining 3 days consumed from annual quota. Total used = 13.0
            self.assertEqual(bal2.carried_forward_used, 10.0)
            self.assertEqual(bal2.used_days, 13.0)
            self.assertEqual(bal2.remaining_days, 12.0)  # 25.0 - 13.0 = 12.0 days remaining

    def test_06_tenant_wide_fy_transition_trigger_endpoint(self):
        """Test the administrative FY transition trigger endpoint."""
        with get_db_context() as db:
            tenant = db.query(Tenant).filter(Tenant.slug == "ssec").first()
            ssec_id = str(tenant.id)

        res = self.client.post(
            "/api/v1/leave/balances/transition-fy?financial_year=2026-2027",
            headers={"X-Tenant-ID": ssec_id},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["financial_year"], "2026-2027")
        self.assertGreaterEqual(data["employees_processed"], 1)
        self.assertGreaterEqual(data["balances_initialized"], 1)


if __name__ == "__main__":
    unittest.main()
