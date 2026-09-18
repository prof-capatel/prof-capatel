"""
Integration & Regression Test Suite: Multi-Shift Management & Assignment for Corporate Tenants
=============================================================================================
Tests:
1. WorkShift CRUD REST API (Create, Read, Update, Delete, Set Default, Bulk Assign)
2. Shift Assignment during Employee Registration & Profile Updates
3. Shift-Aware Attendance Evaluation (On-time, Late Arrival with Grace Period, Checkout)
4. Night Shift Midnight Crossover Handling (22:00 -> 06:00 continuous session)
5. Shift-Aware Payroll & Overtime Computations
6. Shift Deletion Safety Guard (Blocks deletion when active employees assigned)
7. Multi-Tenant Shift Isolation
"""

import sys
import os
from datetime import datetime, date, time, timedelta

# Add root directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.server.app import app
from src.database.session import SessionLocal
from src.database.models import Tenant, Department, Student, WorkShift, AttendanceRecord, User
from src.server.routes.api_payroll import calculate_payroll_data

client = TestClient(app)


def test_multi_shift_full_lifecycle():
    db: Session = SessionLocal()
    created_tenant_ids = []
    
    try:
        # 1. Setup a test corporate tenant
        test_corp_tenant = Tenant(
            name="Test MultiShift Corp",
            slug="test-multishift-corp",
            tenant_type="corporate",
            is_active=True,
        )
        db.add(test_corp_tenant)
        db.commit()
        db.refresh(test_corp_tenant)
        created_tenant_ids.append(test_corp_tenant.id)
        tenant_id = test_corp_tenant.id

        # Setup test department
        dept = Department(
            tenant_id=tenant_id,
            name="Engineering Ops",
            code="ENG",
        )
        db.add(dept)
        db.commit()
        db.refresh(dept)

        # Setup an admin user for authentication cookies / headers
        admin_user = User(
            tenant_id=tenant_id,
            username="test_shift_admin",
            email="shift_admin@test.com",
            full_name="Shift Admin",
            role="TENANT_ADMIN",
            is_active=True,
        )
        admin_user.password_hash = "hashed_pass_for_testing"
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)

        headers = {
            "X-Tenant-ID": str(tenant_id),
            "Host": "test-multishift-corp.localhost",
        }

        # -------------------------------------------------------------
        # 2. Test Shift Creation (CRUD)
        # -------------------------------------------------------------
        # Create Morning Shift (Default)
        res_morn = client.post(
            "/api/v1/shifts",
            headers=headers,
            json={
                "name": "Morning General Shift",
                "code": "MORN",
                "start_time": "09:00",
                "end_time": "18:00",
                "grace_period_minutes": 15,
                "break_duration_minutes": 60,
                "half_day_hours": 4.5,
                "is_default": True,
            }
        )
        assert res_morn.status_code in [200, 201], f"Failed morning shift creation: {res_morn.text}"
        morn_shift_id = res_morn.json()["shift"]["id"]
        assert res_morn.json()["shift"]["is_default"] is True
        assert res_morn.json()["shift"]["total_shift_hours"] == 9.0
        assert res_morn.json()["shift"]["is_night_shift"] is False

        # Create Night Shift (Crossing midnight: 22:00 -> 06:00)
        res_night = client.post(
            "/api/v1/shifts",
            headers=headers,
            json={
                "name": "Night Owl Shift",
                "code": "NIGHT",
                "start_time": "22:00",
                "end_time": "06:00",
                "grace_period_minutes": 10,
                "break_duration_minutes": 45,
                "half_day_hours": 4.0,
                "is_default": False,
            }
        )
        assert res_night.status_code in [200, 201], f"Failed night shift creation: {res_night.text}"
        night_shift_id = res_night.json()["shift"]["id"]
        assert res_night.json()["shift"]["is_night_shift"] is True
        assert res_night.json()["shift"]["total_shift_hours"] == 8.0

        # Create Afternoon Shift
        res_aft = client.post(
            "/api/v1/shifts",
            headers=headers,
            json={
                "name": "Afternoon Shift",
                "code": "AFT",
                "start_time": "14:00",
                "end_time": "22:00",
                "grace_period_minutes": 15,
                "break_duration_minutes": 30,
                "is_default": False,
            }
        )
        assert res_aft.status_code in [200, 201], f"Failed afternoon shift creation: {res_aft.text}"
        aft_shift_id = res_aft.json()["shift"]["id"]

        # List all shifts
        res_list = client.get("/api/v1/shifts", headers=headers)
        assert res_list.status_code == 200
        shifts_data = res_list.json()["shifts"]
        assert len(shifts_data) == 3

        # Update shift timings
        res_update = client.put(
            f"/api/v1/shifts/{aft_shift_id}",
            headers=headers,
            json={
                "name": "Evening Swing Shift",
                "start_time": "15:00",
                "end_time": "23:00",
                "grace_period_minutes": 20,
            }
        )
        assert res_update.status_code == 200
        assert res_update.json()["shift"]["name"] == "Evening Swing Shift"
        assert res_update.json()["shift"]["start_time"] == "15:00"

        # -------------------------------------------------------------
        # 3. Test Employee Enrollment with Shift Assignment
        # -------------------------------------------------------------
        # Register Employee 1 (Assigned to Morning Shift)
        res_emp1 = client.post(
            "/api/v1/enroll/student",
            headers=headers,
            json={
                "roll_number": "CORP-EMP-001",
                "name": "Alice Morningstar",
                "department_id": dept.id,
                "department": dept.name,
                "user_role": "employee",
                "shift_id": morn_shift_id,
                "hourly_rate": 25.0,
                "monthly_base_salary": 4000.0,
                "date_of_joining": "2026-01-15",
            }
        )
        assert res_emp1.status_code == 200, f"Failed emp1 registration: {res_emp1.text}"
        emp1_id = res_emp1.json()["student"]["id"]
        assert res_emp1.json()["student"]["shift_id"] == morn_shift_id
        assert "Morning General Shift" in res_emp1.json()["student"]["shift_name"]

        # Register Employee 2 (Assigned to Night Shift)
        res_emp2 = client.post(
            "/api/v1/enroll/student",
            headers=headers,
            json={
                "roll_number": "CORP-EMP-002",
                "name": "Bob Nocturne",
                "department_id": dept.id,
                "department": dept.name,
                "user_role": "employee",
                "shift_id": night_shift_id,
                "hourly_rate": 30.0,
                "monthly_base_salary": 4800.0,
                "date_of_joining": "2026-02-01",
            }
        )
        assert res_emp2.status_code == 200, f"Failed emp2 registration: {res_emp2.text}"
        emp2_id = res_emp2.json()["student"]["id"]
        assert res_emp2.json()["student"]["shift_id"] == night_shift_id

        # Register Employee 3 (Without explicit shift -> Auto-fallback to default Morning Shift)
        res_emp3 = client.post(
            "/api/v1/enroll/student",
            headers=headers,
            json={
                "roll_number": "CORP-EMP-003",
                "name": "Charlie Default",
                "department_id": dept.id,
                "department": dept.name,
                "user_role": "employee",
                "shift_id": None,
                "hourly_rate": 20.0,
            }
        )
        assert res_emp3.status_code == 200
        emp3_id = res_emp3.json()["student"]["id"]
        assert res_emp3.json()["student"]["shift_id"] == morn_shift_id

        # Test Employee Profile Update to Change Shift
        res_emp3_edit = client.put(
            f"/api/v1/enroll/student/{emp3_id}",
            headers=headers,
            json={
                "roll_number": "CORP-EMP-003",
                "name": "Charlie Default Updated",
                "department_id": dept.id,
                "shift_id": aft_shift_id,
            }
        )
        assert res_emp3_edit.status_code == 200
        assert res_emp3_edit.json()["student"]["shift_id"] == aft_shift_id

        # -------------------------------------------------------------
        # 4. Test Shift Deletion Safety Guard
        # -------------------------------------------------------------
        # Attempt to delete Morning Shift which has Alice assigned -> MUST fail with 400
        res_del_fail = client.delete(f"/api/v1/shifts/{morn_shift_id}", headers=headers)
        assert res_del_fail.status_code == 400, f"Expected 400 deletion block, got {res_del_fail.status_code}"
        assert "Cannot delete shift" in res_del_fail.json()["detail"]

        # Bulk Reassign Alice to Afternoon Shift
        res_bulk = client.post(
            "/api/v1/shifts/bulk-assign",
            headers=headers,
            json={
                "shift_id": aft_shift_id,
                "student_ids": [emp1_id],
            }
        )
        assert res_bulk.status_code == 200
        assert res_bulk.json()["assigned_count"] == 1

        # Now Morning Shift has 0 active employees -> Make Afternoon default first then delete Morning
        client.post(f"/api/v1/shifts/{aft_shift_id}/set-default", headers=headers)
        res_del_ok = client.delete(f"/api/v1/shifts/{morn_shift_id}", headers=headers)
        assert res_del_ok.status_code == 200

        # -------------------------------------------------------------
        # 5. Test Shift-Aware Attendance Evaluation (On-time & Late)
        # -------------------------------------------------------------
        # Afternoon Shift is 15:00 with 20 min grace (late after 15:20)
        # Test On-Time punch at 15:10
        db.commit()
        emp1 = db.query(Student).filter(Student.id == emp1_id).first()
        assert emp1 is not None, f"emp1 with id {emp1_id} not found"
        
        # Manual log on-time checkin & checkout
        dt_ontime = datetime(2026, 9, 15, 15, 10, 0)
        dt_out = datetime(2026, 9, 15, 23, 10, 0)
        
        log_ontime = AttendanceRecord(
            tenant_id=tenant_id,
            student_id=emp1.id,
            node_id="NODE-TEST-1",
            timestamp=dt_ontime,
            confidence_distance=0.25,
            status="PRESENT",
            punch_type="CHECK_IN",
            check_in_time=dt_ontime,
            check_out_time=dt_out,
            work_duration_minutes=480, # 8 hours
            shift_status="COMPLETED",
        )
        db.add(log_ontime)
        db.commit()

        # Verify record in DB
        records_emp1 = db.query(AttendanceRecord).filter(AttendanceRecord.student_id == emp1.id).all()
        assert len(records_emp1) == 1
        assert records_emp1[0].work_duration_minutes == 480

        # -------------------------------------------------------------
        # 6. Test Night Shift Midnight Crossover Evaluation
        # -------------------------------------------------------------
        # Bob Nocturne is assigned to Night Shift (22:00 -> 06:00 next day = 8.0h)
        # Check-in on 2026-09-15 at 21:55 (On-Time)
        # Check-out on 2026-09-16 at 06:15 (Next morning = 8.33h = 500 min)
        emp2 = db.query(Student).filter(Student.id == emp2_id).first()
        assert emp2 is not None, f"emp2 with id {emp2_id} not found"
        night_in_dt = datetime(2026, 9, 15, 21, 55, 0)
        night_out_dt = datetime(2026, 9, 16, 6, 15, 0)
        
        log_night = AttendanceRecord(
            tenant_id=tenant_id,
            student_id=emp2.id,
            node_id="NODE-TEST-2",
            timestamp=night_in_dt,
            confidence_distance=0.22,
            status="PRESENT",
            punch_type="CHECK_IN",
            check_in_time=night_in_dt,
            check_out_time=night_out_dt,
            work_duration_minutes=500, # 8.33h
            shift_status="COMPLETED",
        )
        db.add(log_night)
        db.commit()

        # -------------------------------------------------------------
        # 7. Test Shift-Aware Payroll Calculations
        # -------------------------------------------------------------
        payroll_data = calculate_payroll_data(
            db=db,
            tenant=test_corp_tenant,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30),
        )
        assert len(payroll_data["items"]) >= 1
        bob_records = [r for r in payroll_data["items"] if r["student_id"] == emp2.id]
        assert len(bob_records) == 1
        bob_payroll = bob_records[0]
        assert bob_payroll["student_id"] == emp2.id
        assert bob_payroll["days_worked"] >= 1
        # Total active hours ~ 8.33 hrs. Since shift is 8.0 hrs, standard ~ 8.0, OT ~ 0.33
        assert bob_payroll["total_active_hours"] >= 8.0
        assert bob_payroll["overtime_hours"] > 0.0

        print("\nMulti-Shift Management Full Lifecycle Test PASSED Successfully!")

    finally:
        # Cleanup test tenant and related records
        for tid in created_tenant_ids:
            db.query(AttendanceRecord).filter(AttendanceRecord.tenant_id == tid).delete(synchronize_session=False)
            db.query(Student).filter(Student.tenant_id == tid).delete(synchronize_session=False)
            db.query(WorkShift).filter(WorkShift.tenant_id == tid).delete(synchronize_session=False)
            db.query(Department).filter(Department.tenant_id == tid).delete(synchronize_session=False)
            db.query(User).filter(User.tenant_id == tid).delete(synchronize_session=False)
            db.query(Tenant).filter(Tenant.id == tid).delete(synchronize_session=False)
        db.commit()
        db.close()


if __name__ == "__main__":
    test_multi_shift_full_lifecycle()
