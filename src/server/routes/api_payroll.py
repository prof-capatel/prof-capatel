import io
import json
import logging
from datetime import datetime, date, timedelta, time as dt_time
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import pandas as pd
from sqlalchemy.orm import Session
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from src.database.models import Student, AttendanceRecord, SystemBranding, Tenant, Department, User, LeaveRequest, LeaveType
from src.database.session import get_db
from src.server.tenant_middleware import get_current_tenant, resolve_tenant
from src.server.rbac_middleware import require_roles, check_tenant_operational_access, get_current_user
from src.utils.timezone import get_ist_now, get_ist_date

logger = logging.getLogger("api_payroll")
router = APIRouter(
    prefix="/api/v1/payroll",
    tags=["Corporate Payroll & Wage Management"],
    dependencies=[Depends(require_roles(["SUPER_ADMIN", "TENANT_ADMIN"]))],
)


class EmployeeRateUpdateRequest(BaseModel):
    student_id: int
    hourly_rate: Optional[float] = None
    monthly_base_salary: Optional[float] = None
    cadre_level: Optional[str] = None


class PayrollSettingsUpdateRequest(BaseModel):
    payroll_structure: Optional[str] = "HOURLY"  # HOURLY, MONTHLY_CADRE, HYBRID
    default_hourly_rate: Optional[float] = 15.0
    standard_working_hours_per_day: Optional[float] = 8.0
    enable_overtime: Optional[bool] = True
    overtime_rate_multiplier: Optional[float] = 1.5
    missed_checkout_policy: Optional[str] = "HALF_DAY"  # HALF_DAY, ZERO_HOURS, STANDARD_SHIFT
    currency_symbol: Optional[str] = "₹"


def calculate_payroll_data(
    db: Session,
    tenant: Tenant,
    start_date: date,
    end_date: date,
    department_id: Optional[int] = None,
    user_role: Optional[str] = None,
    search_term: Optional[str] = None,
) -> dict:
    """
    Core business logic engine computing active hours, attendance consistency,
    overtime premiums, missed checkout adjustments, and gross wages per employee.
    """
    start_dt = datetime.combine(start_date, dt_time.min)
    end_dt = datetime.combine(end_date, dt_time.max)
    now = get_ist_now()

    branding = tenant.branding
    payroll_structure = (branding.payroll_structure if branding and branding.payroll_structure else "HOURLY").upper()
    default_hourly_rate = float(branding.default_hourly_rate if branding and branding.default_hourly_rate is not None else 15.0)
    std_daily_hours = float(branding.standard_working_hours_per_day if branding and branding.standard_working_hours_per_day is not None else 8.0)
    enable_overtime = bool(branding.enable_overtime if branding and branding.enable_overtime is not None else True)
    ot_multiplier = float(branding.overtime_rate_multiplier if branding and branding.overtime_rate_multiplier is not None else 1.5)
    missed_policy = (branding.missed_checkout_policy if branding and branding.missed_checkout_policy else "HALF_DAY").upper()
    currency = branding.currency_symbol if branding and branding.currency_symbol else "₹"
    shift_out_str = branding.shift_check_out_time if branding and branding.shift_check_out_time else "18:00"

    # Query active employees in tenant
    emp_query = (
        db.query(Student)
        .filter(Student.tenant_id == tenant.id, Student.is_active == True)
    )

    if department_id:
        emp_query = emp_query.filter(Student.department_id == department_id)

    if user_role:
        emp_query = emp_query.filter(Student.user_role == user_role.strip().lower())

    if search_term:
        term = f"%{search_term.strip()}%"
        emp_query = emp_query.filter(
            (Student.name.ilike(term)) | (Student.roll_number.ilike(term))
        )

    employees = emp_query.order_by(Student.name.asc()).all()

    items = []
    total_billed_hours = 0.0
    total_gross_outlay = 0.0
    total_overtime_outlay = 0.0
    active_employees_count = 0

    # Parse standard shift end time for dynamic missed checkout checking
    try:
        out_parts = shift_out_str.split(":")
        out_h, out_m = int(out_parts[0]), int(out_parts[1])
    except Exception:
        out_h, out_m = 18, 0

    for emp in employees:
        records = (
            db.query(AttendanceRecord)
            .filter(
                AttendanceRecord.tenant_id == tenant.id,
                AttendanceRecord.student_id == emp.id,
                AttendanceRecord.timestamp.between(start_dt, end_dt),
            )
            .order_by(AttendanceRecord.timestamp.asc())
            .all()
        )

        # Resolve Employee specific shift hours & timings
        emp_shift = emp.shift
        emp_std_hours = float(emp_shift.total_shift_hours if emp_shift else std_daily_hours)
        emp_shift_out = emp_shift.end_time if emp_shift else shift_out_str
        is_emp_night = emp_shift.is_night_shift if emp_shift else False
        try:
            emp_out_h, emp_out_m = map(int, emp_shift_out.split(":"))
        except Exception:
            emp_out_h, emp_out_m = 18, 0

        # Group attendance records by calendar date
        daily_records = {}
        for r in records:
            r_date = r.timestamp.date() if r.timestamp else start_date
            if r_date not in daily_records:
                daily_records[r_date] = []
            daily_records[r_date].append(r)

        emp_total_minutes = 0
        emp_standard_hours = 0.0
        emp_overtime_hours = 0.0
        days_worked = len(daily_records)
        missed_checkouts = 0
        late_checkins = 0
        early_departures = 0

        for cal_date, day_recs in daily_records.items():
            day_mins = 0

            for r in day_recs:
                if r.shift_status == "LATE_CHECKIN":
                    late_checkins += 1
                elif r.shift_status == "EARLY_DEPARTURE":
                    early_departures += 1

                if r.check_out_time and r.work_duration_minutes is not None:
                    day_mins += max(0, r.work_duration_minutes)
                elif r.check_in_time and not r.check_out_time:
                    # Open session -> evaluate missed checkout vs active shift
                    target_out_date = cal_date + timedelta(days=1) if is_emp_night else cal_date
                    target_out = datetime.combine(target_out_date, dt_time(hour=emp_out_h, minute=emp_out_m))
                    is_past = (cal_date < now.date() and not is_emp_night) or (is_emp_night and cal_date < now.date() - timedelta(days=1)) or (now > target_out + timedelta(minutes=30))
                    if is_past:
                        missed_checkouts += 1
                        if missed_policy == "HALF_DAY":
                            day_mins += int(emp_std_hours * 0.5 * 60)
                        elif missed_policy == "STANDARD_SHIFT":
                            day_mins += int(emp_std_hours * 60)
                        # ZERO_HOURS adds 0 minutes
                    else:
                        # Ongoing shift today -> credit partial elapsed hours
                        elapsed = int((now - r.check_in_time).total_seconds() / 60)
                        day_mins += max(0, min(int(emp_std_hours * 60), elapsed))

            day_hours = round(day_mins / 60.0, 2)
            emp_total_minutes += day_mins

            if enable_overtime and day_hours > emp_std_hours:
                emp_standard_hours += emp_std_hours
                emp_overtime_hours += round(day_hours - emp_std_hours, 2)
            else:
                emp_standard_hours += day_hours

        # Query approved paid leaves in date range
        approved_leaves = (
            db.query(LeaveRequest)
            .join(LeaveType, LeaveRequest.leave_type_id == LeaveType.id)
            .filter(
                LeaveRequest.tenant_id == tenant.id,
                LeaveRequest.student_id == emp.id,
                LeaveRequest.status == "APPROVED",
                LeaveType.is_paid == True,
                LeaveRequest.start_date <= end_date,
                LeaveRequest.end_date >= start_date,
            )
            .all()
        )
        paid_leave_days = sum(float(l.total_days or 0.0) for l in approved_leaves)
        paid_leave_hours = round(paid_leave_days * emp_std_hours, 2)

        total_emp_hours = round(emp_total_minutes / 60.0, 2)
        total_payable_hours = round(total_emp_hours + paid_leave_hours, 2)
        if total_payable_hours > 0 or days_worked > 0 or paid_leave_days > 0:
            active_employees_count += 1

        effective_rate = float(emp.hourly_rate if emp.hourly_rate is not None else default_hourly_rate)
        
        # Wage Computation
        if payroll_structure == "HOURLY":
            std_pay = round((emp_standard_hours + paid_leave_hours) * effective_rate, 2)
            ot_pay = round(emp_overtime_hours * effective_rate * ot_multiplier, 2) if enable_overtime else 0.0
            gross_pay = round(std_pay + ot_pay, 2)
        elif payroll_structure == "MONTHLY_CADRE":
            base_monthly = float(emp.monthly_base_salary if emp.monthly_base_salary is not None else (effective_rate * emp_std_hours * 22))
            daily_rate = round(base_monthly / 22.0, 2)
            std_pay = round((days_worked + paid_leave_days) * daily_rate, 2)
            ot_pay = round(emp_overtime_hours * effective_rate * ot_multiplier, 2) if enable_overtime else 0.0
            gross_pay = round(std_pay + ot_pay, 2)
        else:  # HYBRID
            base_monthly = float(emp.monthly_base_salary if emp.monthly_base_salary is not None else 0.0)
            std_pay = round(base_monthly + ((emp_standard_hours + paid_leave_hours) * effective_rate), 2)
            ot_pay = round(emp_overtime_hours * effective_rate * ot_multiplier, 2) if enable_overtime else 0.0
            gross_pay = round(std_pay + ot_pay, 2)

        total_billed_hours += total_payable_hours
        total_gross_outlay += gross_pay
        total_overtime_outlay += ot_pay

        items.append({
            "student_id": emp.id,
            "roll_number": emp.roll_number,
            "name": emp.name,
            "department_id": emp.department_id,
            "department": emp.department,
            "user_role": emp.user_role or "employee",
            "cadre_level": emp.cadre_level or "Standard Cadre",
            "shift_id": emp.shift_id,
            "shift_name": emp.shift.name if emp.shift else "Default Shift",
            "shift_timings": f"{emp.shift.start_time} - {emp.shift.end_time}" if emp.shift else f"{branding.shift_check_in_time if branding else '10:30'} - {branding.shift_check_out_time if branding else '18:00'}",
            "days_worked": days_worked,
            "total_active_hours": total_emp_hours,
            "paid_leave_days": round(paid_leave_days, 1),
            "paid_leave_hours": round(paid_leave_hours, 2),
            "total_payable_hours": total_payable_hours,
            "standard_hours": round(emp_standard_hours, 2),
            "overtime_hours": round(emp_overtime_hours, 2),
            "hourly_rate": effective_rate,
            "monthly_base_salary": emp.monthly_base_salary,
            "standard_pay": std_pay,
            "overtime_pay": ot_pay,
            "gross_pay": gross_pay,
            "currency": currency,
            "missed_checkout_count": missed_checkouts,
            "late_checkin_count": late_checkins,
            "early_departure_count": early_departures,
        })

    avg_hourly_payout = round(total_gross_outlay / total_billed_hours, 2) if total_billed_hours > 0 else 0.0

    return {
        "status": "success",
        "tenant_id": tenant.id,
        "tenant_name": tenant.name,
        "date_range": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "days_count": (end_date - start_date).days + 1,
        },
        "config": {
            "payroll_structure": payroll_structure,
            "default_hourly_rate": default_hourly_rate,
            "standard_working_hours_per_day": std_daily_hours,
            "enable_overtime": enable_overtime,
            "overtime_rate_multiplier": ot_multiplier,
            "missed_checkout_policy": missed_policy,
            "currency_symbol": currency,
        },
        "summary": {
            "total_employees": len(employees),
            "active_workforce": active_employees_count,
            "total_billed_hours": round(total_billed_hours, 2),
            "total_gross_outlay": round(total_gross_outlay, 2),
            "total_overtime_outlay": round(total_overtime_outlay, 2),
            "average_hourly_payout": avg_hourly_payout,
            "currency_symbol": currency,
        },
        "items": items,
    }


@router.get("/summary")
def get_payroll_summary(
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    department_id: Optional[int] = Query(None, description="Filter by department ID"),
    user_role: Optional[str] = Query(None, description="Filter by user role"),
    search: Optional[str] = Query(None, description="Search employee name or code"),
    tenant_id: Optional[str] = Query(None, description="Target tenant override for Super Admin"),
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """
    Calculates aggregated employee payroll, working hours, overtime premiums, and gross pay.
    Defaults to current date if range is unspecified.
    """
    target_tenant = current_tenant
    if tenant_id:
        custom_tenant = resolve_tenant(db, tenant_id)
        if custom_tenant:
            target_tenant = custom_tenant

    check_tenant_operational_access(target_tenant)

    today = get_ist_date()
    try:
        s_date = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else today
    except ValueError:
        s_date = today

    try:
        e_date = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else today
    except ValueError:
        e_date = today

    if s_date > e_date:
        s_date, e_date = e_date, s_date

    return calculate_payroll_data(
        db=db,
        tenant=target_tenant,
        start_date=s_date,
        end_date=e_date,
        department_id=department_id,
        user_role=user_role,
        search_term=search,
    )


@router.get("/export")
def export_payroll_report(
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    department_id: Optional[int] = Query(None, description="Filter by department ID"),
    user_role: Optional[str] = Query(None, description="Filter by user role"),
    search: Optional[str] = Query(None, description="Search employee name or code"),
    export_format: str = Query("csv", pattern="^(csv|xlsx)$"),
    tenant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """
    Exports computed payroll and wage summaries to downloadable CSV or professionally styled Excel.
    """
    target_tenant = current_tenant
    if tenant_id:
        custom_tenant = resolve_tenant(db, tenant_id)
        if custom_tenant:
            target_tenant = custom_tenant

    check_tenant_operational_access(target_tenant)

    today = get_ist_date()
    try:
        s_date = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else today
    except ValueError:
        s_date = today

    try:
        e_date = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else today
    except ValueError:
        e_date = today

    if s_date > e_date:
        s_date, e_date = e_date, s_date

    payroll_res = calculate_payroll_data(
        db=db,
        tenant=target_tenant,
        start_date=s_date,
        end_date=e_date,
        department_id=department_id,
        user_role=user_role,
        search_term=search,
    )

    items = payroll_res.get("items", [])
    summary = payroll_res.get("summary", {})
    currency = summary.get("currency_symbol", "₹")

    export_rows = []
    for item in items:
        export_rows.append({
            "Employee Code": item["roll_number"],
            "Full Name": item["name"],
            "Department": item["department"],
            "Designation / Role": item["user_role"].capitalize(),
            "Cadre Level": item["cadre_level"],
            "Days Worked": item["days_worked"],
            "Punch Hours": item["total_active_hours"],
            "Paid Leave Days": item.get("paid_leave_days", 0.0),
            "Paid Leave Hours": item.get("paid_leave_hours", 0.0),
            "Standard Hours": item["standard_hours"],
            "Overtime Hours": item["overtime_hours"],
            "Total Payable Hours": item.get("total_payable_hours", item["total_active_hours"]),
            "Hourly Wage Rate": f"{currency}{item['hourly_rate']:.2f}",
            "Standard Pay": f"{currency}{item['standard_pay']:.2f}",
            "Overtime Pay": f"{currency}{item['overtime_pay']:.2f}",
            "Gross Earnings": f"{currency}{item['gross_pay']:.2f}",
            "Missed Checkouts": item["missed_checkout_count"],
            "Late Arrivals": item["late_checkin_count"],
            "Early Departures": item["early_departure_count"],
        })

    df = pd.DataFrame(export_rows)
    branding = target_tenant.branding
    inst_name = branding.institution_name if branding else target_tenant.name
    short_code = branding.short_code if branding else target_tenant.slug.upper()
    date_label = f"{s_date.strftime('%Y%m%d')}_{e_date.strftime('%Y%m%d')}"

    if export_format == "csv":
        csv_buffer = io.StringIO()
        csv_buffer.write(f"# COMPANY: {inst_name} ({short_code})\n")
        csv_buffer.write(f"# PAYROLL PERIOD: {s_date.isoformat()} to {e_date.isoformat()}\n")
        csv_buffer.write(f"# TOTAL GROSS OUTLAY: {currency}{summary.get('total_gross_outlay', 0.0):.2f} | TOTAL BILLED HOURS: {summary.get('total_billed_hours', 0.0)} hrs\n")
        csv_buffer.write(f"# GENERATED (IST): {get_ist_now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)
        return StreamingResponse(
            io.BytesIO(csv_buffer.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=payroll_{target_tenant.slug}_{date_label}.csv"},
        )
    else:
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Payroll Statement", startrow=4)
            ws = writer.sheets["Payroll Statement"]

            # Header Banner styling
            ws.merge_cells("A1:P1")
            ws["A1"] = f"{inst_name} ({short_code}) — Workforce Payroll Statement"
            ws["A1"].font = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
            ws["A1"].fill = PatternFill(start_color="1E1B4B", end_color="1E1B4B", fill_type="solid")
            ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

            ws.merge_cells("A2:P2")
            ws["A2"] = (
                f"Period: {s_date.isoformat()} to {e_date.isoformat()} | "
                f"Total Gross Outlay: {currency}{summary.get('total_gross_outlay', 0.0):.2f} | "
                f"Billed Hours: {summary.get('total_billed_hours', 0.0)} hrs | "
                f"Active Employees: {summary.get('active_workforce', 0)}"
            )
            ws["A2"].font = Font(name="Calibri", size=10, italic=True)
            ws["A2"].alignment = Alignment(horizontal="center", vertical="center")

        excel_buffer.seek(0)
        return StreamingResponse(
            excel_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=payroll_{target_tenant.slug}_{date_label}.xlsx"},
        )


@router.post("/employee-rate")
def update_employee_rate(
    payload: EmployeeRateUpdateRequest,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """
    Updates individual employee wage rates, base monthly salary, or cadre tier assignment.
    """
    check_tenant_operational_access(current_tenant)
    emp = (
        db.query(Student)
        .filter(Student.id == payload.student_id, Student.tenant_id == current_tenant.id)
        .first()
    )
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found in active tenant organization.")

    if payload.hourly_rate is not None:
        emp.hourly_rate = max(0.0, float(payload.hourly_rate))

    if payload.monthly_base_salary is not None:
        emp.monthly_base_salary = max(0.0, float(payload.monthly_base_salary))

    if payload.cadre_level is not None:
        emp.cadre_level = payload.cadre_level.strip()

    db.commit()
    db.refresh(emp)

    return {
        "status": "success",
        "message": f"Compensation profile updated for '{emp.name}' ({emp.roll_number}).",
        "employee": emp.to_dict(),
    }


@router.post("/settings")
def update_payroll_settings(
    payload: PayrollSettingsUpdateRequest,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """
    Updates organization-wide payroll structure, standard shift hours, and overtime policies.
    """
    check_tenant_operational_access(current_tenant)
    branding = current_tenant.branding
    if not branding:
        branding = SystemBranding(tenant_id=current_tenant.id)
        db.add(branding)

    if payload.payroll_structure:
        branding.payroll_structure = payload.payroll_structure.strip().upper()
    if payload.default_hourly_rate is not None:
        branding.default_hourly_rate = max(0.0, float(payload.default_hourly_rate))
    if payload.standard_working_hours_per_day is not None:
        branding.standard_working_hours_per_day = max(1.0, float(payload.standard_working_hours_per_day))
    if payload.enable_overtime is not None:
        branding.enable_overtime = bool(payload.enable_overtime)
    if payload.overtime_rate_multiplier is not None:
        branding.overtime_rate_multiplier = max(1.0, float(payload.overtime_rate_multiplier))
    if payload.missed_checkout_policy:
        branding.missed_checkout_policy = payload.missed_checkout_policy.strip().upper()
    if payload.currency_symbol:
        branding.currency_symbol = payload.currency_symbol.strip()

    db.commit()
    db.refresh(branding)

    return {
        "status": "success",
        "message": "Payroll settings updated successfully.",
        "branding": branding.to_dict(),
        "config": {
            "payroll_structure": branding.payroll_structure,
            "default_hourly_rate": branding.default_hourly_rate,
            "standard_working_hours_per_day": branding.standard_working_hours_per_day,
            "enable_overtime": branding.enable_overtime,
            "overtime_rate_multiplier": branding.overtime_rate_multiplier,
            "missed_checkout_policy": branding.missed_checkout_policy,
            "currency_symbol": branding.currency_symbol,
        },
    }
