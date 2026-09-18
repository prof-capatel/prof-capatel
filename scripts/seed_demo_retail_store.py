#!/usr/bin/env python3
"""
Demonstration Tenant Seeder for "The Retail Store" (the-retail-store)
Production-grade seeder complete with:
- Tenant & Organization Masters (Branding: Warm Academic Theme, 3 Departments, 1 Location in Ahmedabad)
- 2 Shifts (8:00 AM - 4:00 PM and 12:00 PM - 10:00 PM)
- 4 Statutory Leave Policies & Annual Quotas
- 4 Salary Templates (Structured, Monthly, Daily, Hourly) & Assignments
- 10 Employees with Authentic Indian Names
- Real Biometric Face Encodings cloned from existing system accounts (Chirag, Dhaval, Pranshu, Hiren, MCP, Sachin, etc.)
- August 2026 Check-in & Check-out Attendance Logs
- August 2026 Leave Requests & Approvals
- August 2026 Complete Payroll Batch & Itemized Payslips

Usage:
  python scripts/seed_demo_retail_store.py --seed     # Provisions the demonstration tenant
  python scripts/seed_demo_retail_store.py --purge    # Cleanly purges the demonstration tenant
"""

import sys
import os
import uuid
import json
import random
import argparse
import logging
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from datetime import datetime, date, timedelta
from src.utils.auth_utils import hash_password
from src.database.session import SessionLocal
from src.database.models import (
    Tenant, User, SystemBranding, Department, CompanyLocation, DesignationMaster,
    WorkShift, LeaveType, LeaveBalance, LeaveRequest, SalaryTemplate,
    EmployeeSalaryStructure, Student, FaceEncoding, AttendanceRecord,
    PayrollBatch, PayrollPayslip, AuditLog
)
from src.services.payroll_service import PayrollService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_demo_retail_store")

DEMO_SLUG = "the-retail-store"
DEMO_NAME = "The Retail Store"
DEMO_ACRONYM = "TRS"
DEMO_ADMIN_USER = "admin_retail"
DEMO_ADMIN_PASS = "admin123"


def purge_demo_retail_store(db, verbose: bool = True):
    """Safely purges the demonstration tenant and all its associated records."""
    tenant = db.query(Tenant).filter(Tenant.slug == DEMO_SLUG).first()
    if not tenant:
        if verbose:
            logger.info("Demo tenant '%s' does not exist. Nothing to purge.", DEMO_SLUG)
        return

    tenant_id = tenant.id
    if verbose:
        logger.info("Purging demo tenant ID #%d ('%s')...", tenant_id, tenant.name)

    # 1. Payroll payslips and batches
    payslips_count = db.query(PayrollPayslip).filter(PayrollPayslip.tenant_id == tenant_id).delete(synchronize_session=False)
    batches_count = db.query(PayrollBatch).filter(PayrollBatch.tenant_id == tenant_id).delete(synchronize_session=False)

    # 2. Attendance records
    att_count = db.query(AttendanceRecord).filter(AttendanceRecord.tenant_id == tenant_id).delete(synchronize_session=False)

    # 3. Leave balances and requests
    lreq_count = db.query(LeaveRequest).filter(LeaveRequest.tenant_id == tenant_id).delete(synchronize_session=False)
    lbal_count = db.query(LeaveBalance).filter(LeaveBalance.tenant_id == tenant_id).delete(synchronize_session=False)
    ltype_count = db.query(LeaveType).filter(LeaveType.tenant_id == tenant_id).delete(synchronize_session=False)

    # 4. Face encodings
    enc_count = db.query(FaceEncoding).filter(FaceEncoding.tenant_id == tenant_id).delete(synchronize_session=False)

    # 5. Salary structures, templates, designations
    str_count = db.query(EmployeeSalaryStructure).filter(EmployeeSalaryStructure.tenant_id == tenant_id).delete(synchronize_session=False)
    des_count = db.query(DesignationMaster).filter(DesignationMaster.tenant_id == tenant_id).delete(synchronize_session=False)
    tpl_count = db.query(SalaryTemplate).filter(SalaryTemplate.tenant_id == tenant_id).delete(synchronize_session=False)

    # 6. Employees
    emp_count = db.query(Student).filter(Student.tenant_id == tenant_id).delete(synchronize_session=False)

    # 7. Shifts, Locations, Departments
    shift_count = db.query(WorkShift).filter(WorkShift.tenant_id == tenant_id).delete(synchronize_session=False)
    loc_count = db.query(CompanyLocation).filter(CompanyLocation.tenant_id == tenant_id).delete(synchronize_session=False)
    dept_count = db.query(Department).filter(Department.tenant_id == tenant_id).delete(synchronize_session=False)

    # 8. Branding, Users, Tenant
    db.query(SystemBranding).filter(SystemBranding.tenant_id == tenant_id).delete(synchronize_session=False)
    db.query(AuditLog).filter(AuditLog.tenant_id == tenant_id).delete(synchronize_session=False)
    db.query(User).filter(User.tenant_id == tenant_id).delete(synchronize_session=False)
    db.delete(tenant)

    db.commit()
    if verbose:
        logger.info(
            "Purge Complete: Deleted %d payslips, %d batches, %d attendance logs, %d leaves, %d face encodings, %d employees.",
            payslips_count, batches_count, att_count, lreq_count + lbal_count, enc_count, emp_count
        )


def seed_demo_retail_store(db, verbose: bool = True):
    """Seeds the production-grade demonstration tenant with complete real-world data."""
    # 1. Clean previous demo instance if exists
    purge_demo_retail_store(db, verbose=False)

    logger.info("=================================================================")
    logger.info("   SEEDING DEMO TENANT: 'The Retail Store' (the-retail-store)    ")
    logger.info("=================================================================")

    # 2. Create Tenant
    tenant_uuid = str(uuid.uuid4())
    admin_token = "TRS-ADM-" + uuid.uuid4().hex[:16]
    onboard_token = "TRS-ONB-" + uuid.uuid4().hex[:16]
    att_slug = "trs-checkin-" + uuid.uuid4().hex[:8]

    tenant = Tenant(
        name=DEMO_NAME,
        slug=DEMO_SLUG,
        tenant_type="corporate",
        is_active=True,
        is_deleted=False,
        uuid=tenant_uuid,
        admin_token=admin_token,
        onboarding_token=onboard_token,
        attendance_slug=att_slug
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    tenant_id = tenant.id
    logger.info("[1/8] Created Tenant #%d ('%s') with slug '%s'.", tenant_id, tenant.name, tenant.slug)

    # 3. Create Tenant Administrator User
    admin_user = User(
        tenant_id=tenant_id,
        username=DEMO_ADMIN_USER,
        full_name="Retail Store Administrator",
        email="admin@theretailstore.com",
        password_hash=hash_password(DEMO_ADMIN_PASS),
        role="TENANT_ADMIN",
        is_active=True
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)
    logger.info("[2/8] Created Admin User '%s' with password '%s'.", admin_user.username, DEMO_ADMIN_PASS)

    # 4. Configure System Branding & Security (Warm Academic Theme)
    branding = SystemBranding(
        tenant_id=tenant_id,
        institution_name=DEMO_NAME,
        short_code=DEMO_ACRONYM,
        tagline="Premium Retail & Lifestyle Store - Flagship Ahmedabad",
        primary_accent_color="#c2410c",  # Warm Academic Theme (Terracotta)
        header_badge_text="Retail Flagship Hub",
        contact_email="support@theretailstore.com",
        liveness_mode="off",             # Anti-spoofing Disabled
        enable_anti_spoofing=False,
        cooldown_minutes=1,              # 1-minute sliding attendance cooldown
        enable_self_attendance=False,    # Geofencing / Self-attendance disabled
        overtime_rate_multiplier=1.5,    # 1.5x Overtime
        standard_working_hours_per_day=8.0,
        shift_check_in_time="08:00",
        shift_check_out_time="16:00",
        shift_grace_minutes=15,
        min_checkout_interval_minutes=1,
        payroll_structure="STRUCTURED_SALARY",
        currency_symbol="₹"
    )
    db.add(branding)
    db.commit()
    logger.info("[3/8] Configured Branding: 'Warm Academic' (#c2410c), 1.5x OT, 1-min cooldown, anti-spoofing off.")

    # 5. Create Departments, Location & Shifts
    dept_ops = Department(tenant_id=tenant_id, name="Store Operations", code="DEP-OPS", description="Floor sales, store keeping & visual merchandising")
    dept_inv = Department(tenant_id=tenant_id, name="Inventory & Logistics", code="DEP-INV", description="Warehouse inventory, procurement & logistics")
    dept_cust = Department(tenant_id=tenant_id, name="Customer Experience & Billing", code="DEP-CUST", description="Point of sale cashiering, billing & customer care")
    db.add_all([dept_ops, dept_inv, dept_cust])
    db.commit()

    location_amd = CompanyLocation(
        tenant_id=tenant_id,
        name="Ahmedabad Flagship Store",
        code="LOC-AMD-01",
        city="Ahmedabad",
        state="Gujarat",
        address="Ground Floor, Titanium Square, S.G. Highway, Thaltej, Ahmedabad - 380054",
        contact_number="+91 79 4000 1234",
        is_active=True
    )
    db.add(location_amd)
    db.commit()

    shift_morning = WorkShift(
        tenant_id=tenant_id,
        name="Morning Retail Shift",
        code="SHIFT-MRN",
        start_time="08:00",
        end_time="16:00",
        grace_period_minutes=15,
        break_duration_minutes=60,
        half_day_hours=4.0,
        is_default=True,
        is_active=True
    )
    shift_evening = WorkShift(
        tenant_id=tenant_id,
        name="Evening Retail Shift",
        code="SHIFT-EVE",
        start_time="12:00",
        end_time="22:00",
        grace_period_minutes=15,
        break_duration_minutes=60,
        half_day_hours=5.0,
        is_default=False,
        is_active=True
    )
    db.add_all([shift_morning, shift_evening])
    db.commit()
    logger.info("[4/8] Created 3 Departments, Ahmedabad Location, and 2 Shifts (08:00-16:00 & 12:00-22:00).")

    # 6. Configure 4 Leave Policies
    leave_types_data = [
        ("Casual Leave", "CL", "Short-term personal & casual leaves", True, 12.0),
        ("Medical Leave", "ML", "Health & medical recovery leave", True, 10.0),
        ("Earned Leave", "EL", "Annual accumulated privilege leaves", True, 15.0),
        ("Leave Without Pay", "LWP", "Unpaid authorized absence", False, 30.0),
    ]
    leave_types_map = {}
    for name, code, desc, is_paid, days in leave_types_data:
        lt = LeaveType(
            tenant_id=tenant_id,
            name=name,
            code=code,
            description=desc,
            is_paid=is_paid,
            default_days_per_year=days,
            accrual_frequency="YEARLY",
            is_active=True
        )
        db.add(lt)
        db.commit()
        db.refresh(lt)
        leave_types_map[code] = lt

    # 7. Configure 4 Salary Templates
    tpl_struct = SalaryTemplate(
        tenant_id=tenant_id,
        name="Store Management Grade A (Structured)",
        code="TPL-STRUCT-01",
        compensation_model="STRUCTURED_SALARY",
        description="Full-time managerial compensation with EPF, HRA, Medical & PT",
        basic_percentage=50.0,
        hra_percentage=20.0,
        da_percentage=0.0,
        conveyance_fixed=3000.0,
        medical_fixed=2500.0,
        enable_pf=True,
        pf_capped_at_ceiling=True,
        enable_esi=False,
        enable_pt=True,
        is_active=True
    )
    tpl_monthly = SalaryTemplate(
        tenant_id=tenant_id,
        name="Floor Sales Specialist (Monthly Fixed)",
        code="TPL-MTH-01",
        compensation_model="MONTHLY_FIXED",
        description="Fixed monthly compensation with EPF, ESIC, HRA & PT",
        basic_percentage=60.0,
        hra_percentage=20.0,
        conveyance_fixed=1500.0,
        medical_fixed=1000.0,
        enable_pf=True,
        pf_capped_at_ceiling=True,
        enable_esi=True,
        enable_pt=True,
        is_active=True
    )
    tpl_daily = SalaryTemplate(
        tenant_id=tenant_id,
        name="Temporary Warehouse Associate (Daily Wage)",
        code="TPL-DAILY-01",
        compensation_model="DAILY",
        description="Daily wage compensation with statutory ESI coverage",
        enable_pf=False,
        enable_esi=True,
        enable_pt=False,
        is_active=True
    )
    tpl_hourly = SalaryTemplate(
        tenant_id=tenant_id,
        name="Part-Time Customer Support (Hourly)",
        code="TPL-HRLY-01",
        compensation_model="HOURLY",
        description="Hourly billable wage for flexible shift consultants",
        enable_pf=False,
        enable_esi=False,
        enable_pt=False,
        is_active=True
    )
    db.add_all([tpl_struct, tpl_monthly, tpl_daily, tpl_hourly])
    db.commit()
    logger.info("[5/8] Created 4 Leave Types (CL, ML, EL, LWP) & 4 Salary Templates (Structured, Monthly, Daily, Hourly).")

    # 8. Create Designations
    designations = [
        ("Store Manager", "DES-SM", dept_ops.id, tpl_struct.id),
        ("Assistant Store Manager", "DES-ASM", dept_ops.id, tpl_struct.id),
        ("Floor Manager", "DES-FM", dept_ops.id, tpl_struct.id),
        ("Inventory Lead", "DES-INV", dept_inv.id, tpl_monthly.id),
        ("Logistics Executive", "DES-LOG", dept_inv.id, tpl_daily.id),
        ("Senior Cashier", "DES-CSH", dept_cust.id, tpl_struct.id),
        ("Visual Merchandiser", "DES-VM", dept_ops.id, tpl_monthly.id),
        ("Retail Associate", "DES-RA", dept_ops.id, tpl_daily.id),
        ("Cashier Associate", "DES-CA", dept_cust.id, tpl_hourly.id),
        ("Customer Support Specialist", "DES-CS", dept_cust.id, tpl_hourly.id),
    ]
    des_map = {}
    for title, code, dept_id, tpl_id in designations:
        dm = DesignationMaster(
            tenant_id=tenant_id,
            department_id=dept_id,
            salary_template_id=tpl_id,
            title=title,
            code=code,
            is_active=True
        )
        db.add(dm)
        db.commit()
        db.refresh(dm)
        des_map[code] = dm

    # 9. Map 10 Authentic Employees with Real Face Vector Sources
    # Sources:
    # 1. Chirag Patel (student ID 2, Tenant 1)
    # 2. Dhaval Shah (student ID 13, Tenant 1)
    # 3. Pranshu Patel (student ID 80, Tenant 1)
    # 4. Hiren Parmar (student ID 89, Tenant 1)
    # 5. Mayur Patel (student ID 7, Tenant 1)
    # 6. Sachin Dave (student ID 11, Tenant 1)
    # 7. Vijay Patel (student ID 3, Tenant 1)
    # 8. Sagar Patel (student ID 8, Tenant 1)
    # 9. Het Patel (student ID 681, Tenant 106)
    # 10. Anand Parekh (student ID 472, Tenant 292)
    employee_specs = [
        {
            "name": "Chirag Patel",
            "roll": "TRS-EMP-01",
            "email": "chirag.patel@theretailstore.com",
            "dept": dept_ops.name,
            "des_code": "DES-SM",
            "shift_id": shift_morning.id,
            "source_student_id": 2,
            "model": "STRUCTURED_SALARY",
            "monthly_gross": 50000.0,
            "annual_ctc": 600000.0,
            "basic": 25000.0,
            "hra": 10000.0,
            "conv": 3000.0,
            "med": 2500.0,
            "spec": 9500.0,
            "enable_pf": True, "enable_esi": False, "enable_pt": True,
            "daily_rate": None, "hourly_rate": None,
            "template_id": tpl_struct.id
        },
        {
            "name": "Dhaval Shah",
            "roll": "TRS-EMP-02",
            "email": "dhaval.shah@theretailstore.com",
            "dept": dept_inv.name,
            "des_code": "DES-INV",
            "shift_id": shift_morning.id,
            "source_student_id": 13,
            "model": "MONTHLY_FIXED",
            "monthly_gross": 32000.0,
            "annual_ctc": 384000.0,
            "basic": 19200.0,
            "hra": 6400.0,
            "conv": 1500.0,
            "med": 1000.0,
            "spec": 3900.0,
            "enable_pf": True, "enable_esi": True, "enable_pt": True,
            "daily_rate": None, "hourly_rate": None,
            "template_id": tpl_monthly.id
        },
        {
            "name": "Pranshu Patel",
            "roll": "TRS-EMP-03",
            "email": "pranshu.patel@theretailstore.com",
            "dept": dept_cust.name,
            "des_code": "DES-CSH",
            "shift_id": shift_morning.id,
            "source_student_id": 80,
            "model": "STRUCTURED_SALARY",
            "monthly_gross": 28000.0,
            "annual_ctc": 336000.0,
            "basic": 14000.0,
            "hra": 5600.0,
            "conv": 2000.0,
            "med": 1500.0,
            "spec": 4900.0,
            "enable_pf": True, "enable_esi": True, "enable_pt": True,
            "daily_rate": None, "hourly_rate": None,
            "template_id": tpl_struct.id
        },
        {
            "name": "Hiren Parmar",
            "roll": "TRS-EMP-04",
            "email": "hiren.parmar@theretailstore.com",
            "dept": dept_ops.name,
            "des_code": "DES-FM",
            "shift_id": shift_evening.id,
            "source_student_id": 89,
            "model": "STRUCTURED_SALARY",
            "monthly_gross": 42000.0,
            "annual_ctc": 504000.0,
            "basic": 21000.0,
            "hra": 8400.0,
            "conv": 2500.0,
            "med": 2000.0,
            "spec": 8100.0,
            "enable_pf": True, "enable_esi": False, "enable_pt": True,
            "daily_rate": None, "hourly_rate": None,
            "template_id": tpl_struct.id
        },
        {
            "name": "Mayur Patel",
            "roll": "TRS-EMP-05",
            "email": "mayur.patel@theretailstore.com",
            "dept": dept_ops.name,
            "des_code": "DES-VM",
            "shift_id": shift_evening.id,
            "source_student_id": 7,
            "model": "MONTHLY_FIXED",
            "monthly_gross": 26000.0,
            "annual_ctc": 312000.0,
            "basic": 15600.0,
            "hra": 5200.0,
            "conv": 1500.0,
            "med": 1000.0,
            "spec": 2700.0,
            "enable_pf": True, "enable_esi": True, "enable_pt": True,
            "daily_rate": None, "hourly_rate": None,
            "template_id": tpl_monthly.id
        },
        {
            "name": "Sachin Dave",
            "roll": "TRS-EMP-06",
            "email": "sachin.dave@theretailstore.com",
            "dept": dept_ops.name,
            "des_code": "DES-RA",
            "shift_id": shift_morning.id,
            "source_student_id": 11,
            "model": "DAILY",
            "monthly_gross": 24700.0,
            "annual_ctc": 296400.0,
            "basic": 0.0, "hra": 0.0, "conv": 0.0, "med": 0.0, "spec": 0.0,
            "enable_pf": False, "enable_esi": True, "enable_pt": False,
            "daily_rate": 950.0, "hourly_rate": None,
            "template_id": tpl_daily.id
        },
        {
            "name": "Vijay Patel",
            "roll": "TRS-EMP-07",
            "email": "vijay.patel@theretailstore.com",
            "dept": dept_inv.name,
            "des_code": "DES-LOG",
            "shift_id": shift_morning.id,
            "source_student_id": 3,
            "model": "DAILY",
            "monthly_gross": 23400.0,
            "annual_ctc": 280800.0,
            "basic": 0.0, "hra": 0.0, "conv": 0.0, "med": 0.0, "spec": 0.0,
            "enable_pf": False, "enable_esi": True, "enable_pt": False,
            "daily_rate": 900.0, "hourly_rate": None,
            "template_id": tpl_daily.id
        },
        {
            "name": "Sagar Patel",
            "roll": "TRS-EMP-08",
            "email": "sagar.patel@theretailstore.com",
            "dept": dept_cust.name,
            "des_code": "DES-CA",
            "shift_id": shift_evening.id,
            "source_student_id": 8,
            "model": "HOURLY",
            "monthly_gross": 25600.0,
            "annual_ctc": 307200.0,
            "basic": 0.0, "hra": 0.0, "conv": 0.0, "med": 0.0, "spec": 0.0,
            "enable_pf": False, "enable_esi": False, "enable_pt": False,
            "daily_rate": None, "hourly_rate": 160.0,
            "template_id": tpl_hourly.id
        },
        {
            "name": "Het Patel",
            "roll": "TRS-EMP-09",
            "email": "het.patel@theretailstore.com",
            "dept": dept_cust.name,
            "des_code": "DES-CS",
            "shift_id": shift_evening.id,
            "source_student_id": 681,
            "model": "HOURLY",
            "monthly_gross": 24000.0,
            "annual_ctc": 288000.0,
            "basic": 0.0, "hra": 0.0, "conv": 0.0, "med": 0.0, "spec": 0.0,
            "enable_pf": False, "enable_esi": False, "enable_pt": False,
            "daily_rate": None, "hourly_rate": 150.0,
            "template_id": tpl_hourly.id
        },
        {
            "name": "Anand Parekh",
            "roll": "TRS-EMP-10",
            "email": "anand.parekh@theretailstore.com",
            "dept": dept_ops.name,
            "des_code": "DES-ASM",
            "shift_id": shift_evening.id,
            "source_student_id": 472,
            "model": "STRUCTURED_SALARY",
            "monthly_gross": 38000.0,
            "annual_ctc": 456000.0,
            "basic": 19000.0,
            "hra": 7600.0,
            "conv": 2500.0,
            "med": 2000.0,
            "spec": 6900.0,
            "enable_pf": True, "enable_esi": False, "enable_pt": True,
            "daily_rate": None, "hourly_rate": None,
            "template_id": tpl_struct.id
        },
    ]

    seeded_employees = []
    total_vectors_cloned = 0

    for spec in employee_specs:
        dm = des_map[spec["des_code"]]
        emp = Student(
            tenant_id=tenant_id,
            name=spec["name"],
            roll_number=spec["roll"],
            email=spec["email"],
            department=spec["dept"],
            designation=dm.title,
            designation_id=dm.id,
            location_id=location_amd.id,
            shift_id=spec["shift_id"],
            user_role="employee",
            employment_status="ACTIVE",
            date_of_joining=date(2026, 1, 1),
            monthly_base_salary=spec["monthly_gross"],
            hourly_rate=spec["hourly_rate"] or 0.0,
            pan_number=f"ABCDE{random.randint(1000, 9999)}F",
            uan_number=f"101{random.randint(100000000, 999999999)}",
            bank_name="HDFC Bank",
            bank_account_number=f"50100{random.randint(1000000, 9999999)}",
            bank_ifsc_code="HDFC0001234",
            is_active=True
        )
        db.add(emp)
        db.commit()
        db.refresh(emp)
        seeded_employees.append(emp)

        # Assign Salary Structure
        sal_struct = EmployeeSalaryStructure(
            tenant_id=tenant_id,
            student_id=emp.id,
            template_id=spec["template_id"],
            compensation_model=spec["model"],
            monthly_gross=spec["monthly_gross"],
            annual_ctc=spec["annual_ctc"],
            monthly_basic=spec["basic"],
            monthly_hra=spec["hra"],
            conveyance_allowance=spec["conv"],
            medical_allowance=spec["med"],
            special_allowance=spec["spec"],
            other_allowances=0.0,
            daily_rate=spec["daily_rate"],
            hourly_rate=spec["hourly_rate"],
            enable_pf=spec["enable_pf"],
            pf_capped_at_ceiling=True,
            enable_esi=spec["enable_esi"],
            enable_pt=spec["enable_pt"],
            pt_monthly_amount=200.0 if spec["enable_pt"] else 0.0,
            effective_from_date=date(2026, 1, 1),
            is_current=True,
            revision_reason="Initial demo onboarding structure"
        )
        db.add(sal_struct)

        # Initialize 4 Leave Balances
        for code, lt in leave_types_map.items():
            lb = LeaveBalance(
                tenant_id=tenant_id,
                student_id=emp.id,
                leave_type_id=lt.id,
                year=2026,
                total_allocated=lt.default_days_per_year,
                used_days=0.0,
                pending_days=0.0,
                remaining_days=lt.default_days_per_year
            )
            db.add(lb)

        # Clone Real Biometric Face Encodings from Source Student
        source_encs = db.query(FaceEncoding).filter(FaceEncoding.student_id == spec["source_student_id"]).all()
        for src_enc in source_encs:
            cloned_enc = FaceEncoding(
                tenant_id=tenant_id,
                student_id=emp.id,
                sample_angle=src_enc.sample_angle,
                vector_json=src_enc.vector_json,
                photo_path=src_enc.photo_path
            )
            db.add(cloned_enc)
            total_vectors_cloned += 1

        db.commit()

    logger.info(
        "[6/8] Provisioned 10 Employees with Salary Structures, Quotas, and Cloned %d Real Face Encodings.",
        total_vectors_cloned
    )

    # 10. Generate August 2026 Leave Requests
    leave_requests_plan = [
        # (emp_idx, leave_code, start_d, end_d, is_half, status, reason)
        (0, "CL", 14, 14, False, "APPROVED", "Family social function in Ahmedabad"),
        (1, "ML", 10, 11, False, "APPROVED", "Severe viral fever and medical recovery"),
        (2, "EL", 21, 22, False, "APPROVED", "Annual planned family vacation"),
        (4, "CL", 28, 28, False, "APPROVED", "Personal household errands"),
        (5, "CL", 5, 5, False, "PENDING", "Festival holiday leave (Pending HR approval)"),
        (7, "ML", 18, 18, False, "REJECTED", "Short medical absence without prescription"),
    ]

    approved_leave_days_by_emp = {emp.id: set() for emp in seeded_employees}

    for emp_idx, code, start_day, end_day, is_half, status_val, reason_str in leave_requests_plan:
        emp = seeded_employees[emp_idx]
        lt = leave_types_map[code]
        s_date = date(2026, 8, start_day)
        e_date = date(2026, 8, end_day)
        tot_days = 0.5 if is_half else (end_day - start_day + 1)

        req = LeaveRequest(
            tenant_id=tenant_id,
            student_id=emp.id,
            leave_type_id=lt.id,
            start_date=s_date,
            end_date=e_date,
            is_half_day=is_half,
            half_day_period="FIRST_HALF" if is_half else "NONE",
            total_days=tot_days,
            reason=reason_str,
            status=status_val,
            reviewed_by_user_id=admin_user.id if status_val != "PENDING" else None,
            reviewed_at=datetime(2026, 8, max(1, start_day - 1), 10, 0, 0) if status_val != "PENDING" else None,
            admin_remarks="Approved by Store HR" if status_val == "APPROVED" else ("Rejected - insufficient documentation" if status_val == "REJECTED" else None)
        )
        db.add(req)
        db.commit()

        # Update LeaveBalance
        bal = db.query(LeaveBalance).filter(
            LeaveBalance.tenant_id == tenant_id,
            LeaveBalance.student_id == emp.id,
            LeaveBalance.leave_type_id == lt.id,
            LeaveBalance.year == 2026
        ).first()

        if bal:
            if status_val == "APPROVED":
                bal.used_days += tot_days
                bal.remaining_days = max(0.0, bal.total_allocated - bal.used_days)
                # Track for attendance simulation
                curr = s_date
                while curr <= e_date:
                    approved_leave_days_by_emp[emp.id].add(curr)
                    curr += timedelta(days=1)
            elif status_val == "PENDING":
                bal.pending_days += tot_days

        db.commit()

    # 11. Generate Full August 2026 Attendance Logs (Aug 1 - Aug 31)
    august_start = date(2026, 8, 1)
    august_end = date(2026, 8, 31)
    current_day = august_start
    total_punches_seeded = 0

    while current_day <= august_end:
        day_of_week = current_day.weekday()  # 0=Monday, 6=Sunday
        is_sunday = (day_of_week == 6)

        if not is_sunday:
            for emp in seeded_employees:
                # If on approved leave, skip physical punch (handled as leave credit)
                if current_day in approved_leave_days_by_emp[emp.id]:
                    continue

                # Determine shift times
                is_morning = (emp.shift_id == shift_morning.id)
                if is_morning:
                    # Morning Shift: 08:00 - 16:00
                    # Check-in: 07:50 - 08:12
                    in_min_offset = random.randint(-10, 12)
                    in_time = datetime(2026, 8, current_day.day, 8, 0, 0) + timedelta(minutes=in_min_offset)
                    
                    # Check-out: 16:05 - 16:45 (occasional OT till 17:30)
                    out_min_offset = random.randint(5, 45) if random.random() > 0.25 else random.randint(50, 90)
                    out_time = datetime(2026, 8, current_day.day, 16, 0, 0) + timedelta(minutes=out_min_offset)
                else:
                    # Evening Shift: 12:00 - 22:00
                    in_min_offset = random.randint(-8, 14)
                    in_time = datetime(2026, 8, current_day.day, 12, 0, 0) + timedelta(minutes=in_min_offset)
                    
                    # Check-out: 22:02 - 22:45
                    out_min_offset = random.randint(2, 45)
                    out_time = datetime(2026, 8, current_day.day, 22, 0, 0) + timedelta(minutes=out_min_offset)

                duration_mins = int((out_time - in_time).total_seconds() // 60)
                shift_status = "ON_TIME" if in_min_offset <= 15 else "LATE_CHECKIN"

                att_rec = AttendanceRecord(
                    tenant_id=tenant_id,
                    student_id=emp.id,
                    node_id="NODE-RETAIL-MAIN-01",
                    timestamp=in_time,
                    confidence_distance=round(random.uniform(0.32, 0.41), 4),
                    status="PRESENT",
                    punch_type="CHECK_IN",
                    check_in_time=in_time,
                    check_out_time=out_time,
                    work_duration_minutes=duration_mins,
                    shift_status=shift_status,
                    is_manual_override=False
                )
                db.add(att_rec)
                total_punches_seeded += 1

        current_day += timedelta(days=1)

    db.commit()
    logger.info(
        "[7/8] Generated %d August 2026 Attendance Punches & 6 Leave Requests for all 10 Employees.",
        total_punches_seeded
    )

    # 12. Calculate and Generate August 2026 Payroll Batch & Itemized Payslips
    try:
        class BatchPayload:
            period_month = 8
            period_year = 2026
            start_date = None
            end_date = None
            working_days = 26.0
            department_id = None

        ps = PayrollService(db)
        batch_res = ps.generate_batch(tenant=tenant, payload=BatchPayload(), current_user=admin_user)
        batch_id = batch_res.get("data", {}).get("id")
        
        if batch_id:
            payroll_batch = db.query(PayrollBatch).filter(PayrollBatch.id == batch_id).first()
            payroll_batch.status = "DISBURSED"
            payroll_batch.approved_by_user_id = admin_user.id
            payroll_batch.approved_at = datetime(2026, 9, 1, 10, 0, 0)
            payroll_batch.disbursed_by_user_id = admin_user.id
            payroll_batch.disbursed_at = datetime(2026, 9, 2, 14, 30, 0)
            
            # Also set payslips payment_status to PAID
            db.query(PayrollPayslip).filter(PayrollPayslip.batch_id == batch_id).update(
                {"payment_status": "PAID", "payment_date": date(2026, 9, 2)},
                synchronize_session=False
            )
            db.commit()
            
            payslips_count = db.query(PayrollPayslip).filter(PayrollPayslip.batch_id == batch_id).count()
            logger.info(
                "[8/8] Generated August 2026 Payroll Batch #%s with %d Itemized Payslips (Total Gross: ₹%.2f, Net: ₹%.2f).",
                payroll_batch.batch_number, payslips_count, payroll_batch.total_gross_outlay, payroll_batch.total_net_outlay
            )
        else:
            logger.warning("Payroll batch response did not return batch ID: %s", batch_res)
    except Exception as e:
        logger.error("Failed to generate August 2026 payroll batch: %s", e, exc_info=True)
        db.rollback()

    logger.info("=================================================================")
    logger.info("   DEMO TENANT 'The Retail Store' SEEDED SUCCESSFULLY!          ")
    logger.info("   Tenant URL: /portal/%s                                       ", DEMO_SLUG)
    logger.info("   Admin Login: %s / %s                                         ", DEMO_ADMIN_USER, DEMO_ADMIN_PASS)
    logger.info("   Employee Face Portal: /employee/%s                           ", DEMO_SLUG)
    logger.info("=================================================================")


def main():
    parser = argparse.ArgumentParser(description="Demonstration Tenant Seeder for 'The Retail Store'")
    parser.add_argument("--seed", action="store_true", help="Seed the complete demonstration tenant")
    parser.add_argument("--purge", action="store_true", help="Purge the demonstration tenant")

    args = parser.parse_args()
    db = SessionLocal()
    try:
        if args.purge:
            purge_demo_retail_store(db, verbose=True)
        elif args.seed:
            seed_demo_retail_store(db, verbose=True)
        else:
            parser.print_help()
    finally:
        db.close()


if __name__ == "__main__":
    main()
