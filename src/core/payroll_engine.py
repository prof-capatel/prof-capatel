"""
==============================================================================
Indian-Context Enterprise Payroll & Compensation Calculation Engine
==============================================================================
Provides high-precision payroll computation for multi-model compensation:
- STRUCTURED_SALARY (CTC Breakdown: Basic, DA, HRA, Conveyance, Medical, Special)
- MONTHLY_FIXED (Monthly base with working-days pro-rating)
- HOURLY (Biometric hours worked + configurable OT)
- DAILY_WAGE (Daily rate * present days)
- STIPEND (Fixed intern stipend minus LWP)
- CONTRACT, COMMISSION, and HYBRID structures

Statutory Deductions & Liabilities (Indian Compliance):
- Employee Provident Fund (EPF): 12% on Basic+DA with statutory ceiling toggle (₹15,000/mo cap).
- Employer PF / EPS: 3.67% EPF + 8.33% EPS.
- Employee State Insurance (ESIC): 0.75% Employee + 3.25% Employer (Gross <= ₹21,000).
- Professional Tax (PT): Configurable state/monthly flat deduction (default ₹200/mo).
- Tax Deducted at Source (TDS), Loan/Salary Advance recovery.
- Mid-Month Salary Revision Pro-Rating support (Option 3A).
==============================================================================
"""

import json
import logging
from datetime import datetime, date, timedelta, time as dt_time
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session

from src.database.models import (
    Tenant,
    Student,
    AttendanceRecord,
    SystemBranding,
    LeaveRequest,
    LeaveType,
    WorkShift,
    EmployeeSalaryStructure,
    SalaryTemplate,
    SalaryRevisionHistory,
    PayrollBatch,
    PayrollPayslip,
    User,
)
from src.utils.timezone import get_ist_now, get_ist_date

logger = logging.getLogger("payroll_engine")


def number_to_words_inr(amount: float) -> str:
    """
    Converts a monetary amount into formal Indian English words (Lakhs, Crores).
    e.g. 45250.00 -> 'Rupees Forty-Five Thousand Two Hundred Fifty Only'
    """
    if amount is None or amount == 0:
        return "Rupees Zero Only"

    try:
        amount_val = round(float(amount), 2)
        rupees = int(amount_val)
        paise = int(round((amount_val - rupees) * 100))

        ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
                "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
                "Seventeen", "Eighteen", "Nineteen"]
        tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

        def _two_digits(n: int) -> str:
            if n < 20:
                return ones[n]
            t = tens[n // 10]
            o = ones[n % 10]
            return f"{t}-{o}" if o else t

        def _three_digits(n: int) -> str:
            h = n // 100
            rem = n % 100
            res = ""
            if h > 0:
                res += f"{ones[h]} Hundred"
                if rem > 0:
                    res += " and "
            if rem > 0:
                res += _two_digits(rem)
            return res.strip()

        # Indian Numbering Place Values: Crores (1,00,00,000), Lakhs (1,00,000), Thousands (1,000), Hundreds (100)
        crores = rupees // 10000000
        rem_crores = rupees % 10000000
        lakhs = rem_crores // 100000
        rem_lakhs = rem_crores % 100000
        thousands = rem_lakhs // 1000
        hundreds = rem_lakhs % 1000

        words = []
        if crores > 0:
            words.append(f"{_three_digits(crores)} Crore")
        if lakhs > 0:
            words.append(f"{_three_digits(lakhs)} Lakh")
        if thousands > 0:
            words.append(f"{_three_digits(thousands)} Thousand")
        if hundreds > 0:
            words.append(_three_digits(hundreds))

        rupees_str = " ".join(words) if words else "Zero"
        res_str = f"Rupees {rupees_str}"

        if paise > 0:
            res_str += f" and {_two_digits(paise)} Paise"

        return f"{res_str} Only"
    except Exception as e:
        logger.warning(f"Error converting number to words for {amount}: {e}")
        return f"Rupees {amount:.2f} Only"


def get_effective_salary_structures(
    db: Session,
    tenant_id: int,
    student: Student,
    start_date: date,
    end_date: date,
) -> List[Tuple[date, date, EmployeeSalaryStructure, float]]:
    """
    Identifies all effective salary structures for the employee during [start_date, end_date].
    Handles Mid-Month Salary Revisions (Option 3A) by dividing the period into sub-segments.
    Returns a list of tuples: (segment_start_date, segment_end_date, structure_obj, segment_day_count).
    """
    structures = (
        db.query(EmployeeSalaryStructure)
        .filter(
            EmployeeSalaryStructure.tenant_id == tenant_id,
            EmployeeSalaryStructure.student_id == student.id,
            EmployeeSalaryStructure.effective_from_date <= end_date,
            (EmployeeSalaryStructure.effective_to_date == None) | (EmployeeSalaryStructure.effective_to_date >= start_date),
        )
        .order_by(EmployeeSalaryStructure.effective_from_date.asc())
        .all()
    )

    total_period_days = (end_date - start_date).days + 1

    if not structures:
        # Build an on-the-fly default fallback structure from student or branding
        branding = student.tenant.branding if (student.tenant and student.tenant.branding) else None
        p_structure = (branding.payroll_structure if branding and branding.payroll_structure else "HOURLY").upper()
        h_rate = float(student.hourly_rate or (branding.default_hourly_rate if branding else 15.0) or 15.0)
        m_base = float(student.monthly_base_salary or (h_rate * 8.0 * 26.0 if p_structure == "HOURLY" else 35000.0))

        fallback = EmployeeSalaryStructure(
            tenant_id=tenant_id,
            student_id=student.id,
            compensation_model=p_structure,
            annual_ctc=m_base * 12.0,
            monthly_gross=m_base,
            monthly_basic=round(m_base * 0.50, 2),
            monthly_da=0.0,
            monthly_hra=round(m_base * 0.20, 2),
            conveyance_allowance=1600.0 if m_base > 20000 else 0.0,
            medical_allowance=1250.0 if m_base > 20000 else 0.0,
            special_allowance=round(max(0.0, m_base - (m_base * 0.70 + 2850.0)), 2),
            other_allowances=0.0,
            hourly_rate=h_rate,
            daily_rate=round(m_base / 26.0, 2),
            fixed_stipend=m_base if p_structure == "STIPEND" else 0.0,
            commission_percentage=0.0,
            enable_pf=True,
            pf_capped_at_ceiling=True,
            enable_esi=True,
            enable_pt=True,
            pt_monthly_amount=float(branding.pt_monthly_default if branding and branding.pt_monthly_default is not None else 200.0),
            tds_monthly_amount=0.0,
            effective_from_date=start_date,
            effective_to_date=None,
            is_current=True,
        )
        return [(start_date, end_date, fallback, float(total_period_days))]

    segments = []
    for st in structures:
        seg_start = max(start_date, st.effective_from_date)
        seg_end = min(end_date, st.effective_to_date) if st.effective_to_date else end_date
        if seg_start <= seg_end:
            seg_days = (seg_end - seg_start).days + 1
            segments.append((seg_start, seg_end, st, float(seg_days)))

    if not segments:
        fallback = structures[-1]
        segments.append((start_date, end_date, fallback, float(total_period_days)))

    return segments


def calculate_employee_payroll(
    db: Session,
    tenant: Tenant,
    student: Student,
    start_date: date,
    end_date: date,
    total_working_days: float = 26.0,
    bonus_incentives: float = 0.0,
    advance_loan_deduction: float = 0.0,
    other_deductions_manual: float = 0.0,
    payment_method: str = "BANK_TRANSFER",
    remarks: str = "",
) -> Dict[str, Any]:
    """
    Computes full Indian-context payroll for an individual employee across the given period,
    handling statutory liabilities (EPF, ESIC, PT, TDS), overtime, and pro-rata revisions.
    """
    start_dt = datetime.combine(start_date, dt_time.min)
    end_dt = datetime.combine(end_date, dt_time.max)
    now = get_ist_now()

    branding = tenant.branding
    std_daily_hours = float(branding.standard_working_hours_per_day if branding and branding.standard_working_hours_per_day is not None else 8.0)
    enable_overtime = bool(branding.enable_overtime if branding and branding.enable_overtime is not None else True)
    ot_multiplier = float(branding.overtime_rate_multiplier if branding and branding.overtime_rate_multiplier is not None else 1.5)
    holiday_ot_multiplier = float(branding.holiday_ot_multiplier if branding and branding.holiday_ot_multiplier is not None else 2.0)
    missed_policy = (branding.missed_checkout_policy if branding and branding.missed_checkout_policy else "HALF_DAY").upper()
    currency = branding.currency_symbol if branding and branding.currency_symbol else "₹"
    shift_out_str = branding.shift_check_out_time if branding and branding.shift_check_out_time else "18:00"

    # 1. Fetch Attendance Records for this employee
    records = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.tenant_id == tenant.id,
            AttendanceRecord.student_id == student.id,
            AttendanceRecord.timestamp.between(start_dt, end_dt),
        )
        .order_by(AttendanceRecord.timestamp.asc())
        .all()
    )

    # 2. Fetch Approved Leave Requests
    approved_leaves = (
        db.query(LeaveRequest)
        .filter(
            LeaveRequest.tenant_id == tenant.id,
            LeaveRequest.student_id == student.id,
            LeaveRequest.status == "APPROVED",
            LeaveRequest.start_date <= end_date,
            LeaveRequest.end_date >= start_date,
        )
        .all()
    )

    paid_leave_days = 0.0
    unpaid_leave_days = 0.0
    for lr in approved_leaves:
        l_start = max(start_date, lr.start_date)
        l_end = min(end_date, lr.end_date)
        overlap_days = max(0, (l_end - l_start).days + 1)
        if lr.is_half_day:
            duration = 0.5
        else:
            duration = float(overlap_days)

        if lr.leave_type and lr.leave_type.is_paid:
            paid_leave_days += duration
        else:
            unpaid_leave_days += duration

    # 3. Resolve shift details
    emp_shift = student.shift
    emp_std_hours = float(emp_shift.total_shift_hours if emp_shift else std_daily_hours)
    emp_shift_out = emp_shift.end_time if emp_shift else shift_out_str
    is_emp_night = emp_shift.is_night_shift if emp_shift else False
    try:
        emp_out_h, emp_out_m = map(int, emp_shift_out.split(":"))
    except Exception:
        emp_out_h, emp_out_m = 18, 0

    # 4. Group attendance by date
    daily_records: Dict[date, List[AttendanceRecord]] = {}
    for r in records:
        r_date = r.timestamp.date() if r.timestamp else start_date
        if r_date not in daily_records:
            daily_records[r_date] = []
        daily_records[r_date].append(r)

    total_billed_minutes = 0
    total_regular_ot_hours = 0.0
    total_holiday_ot_hours = 0.0
    present_days_count = 0.0
    missed_checkouts = 0
    late_checkins = 0
    early_departures = 0

    for cal_date, day_recs in daily_records.items():
        day_mins = 0
        is_holiday_shift = (cal_date.weekday() >= 5) # Saturday / Sunday as weekend overtime

        for r in day_recs:
            if r.shift_status == "LATE_CHECKIN":
                late_checkins += 1
            elif r.shift_status == "EARLY_DEPARTURE":
                early_departures += 1

            if r.check_out_time and r.work_duration_minutes is not None:
                day_mins += max(0, r.work_duration_minutes)
            elif r.check_in_time and not r.check_out_time:
                target_out_date = cal_date + timedelta(days=1) if is_emp_night else cal_date
                target_out = datetime.combine(target_out_date, dt_time(hour=emp_out_h, minute=emp_out_m))
                is_past = (cal_date < now.date() and not is_emp_night) or (is_emp_night and cal_date < now.date() - timedelta(days=1)) or (now > target_out + timedelta(minutes=30))
                if is_past:
                    missed_checkouts += 1
                    if missed_policy == "HALF_DAY":
                        day_mins += int(emp_std_hours * 30)
                    elif missed_policy == "STANDARD_SHIFT":
                        day_mins += int(emp_std_hours * 60)
                else:
                    # In-progress shift
                    elapsed = max(0, int((now - r.timestamp).total_seconds() / 60))
                    day_mins += min(int(emp_std_hours * 60), elapsed)

        day_hours = day_mins / 60.0
        total_billed_minutes += day_mins

        if day_hours > 0:
            if day_hours >= (emp_std_hours * 0.7):
                present_days_count += 1.0
            elif day_hours >= (emp_std_hours * 0.35):
                present_days_count += 0.5
            else:
                present_days_count += round(day_hours / emp_std_hours, 2)

        # Overtime computation
        if enable_overtime and day_hours > emp_std_hours:
            ot_h = round(day_hours - emp_std_hours, 2)
            if is_holiday_shift:
                total_holiday_ot_hours += ot_h
            else:
                total_regular_ot_hours += ot_h

    total_billed_hours = round(total_billed_minutes / 60.0, 2)
    calendar_days_count = (end_date - start_date).days + 1
    absent_days_count = max(0.0, round(total_working_days - (present_days_count + paid_leave_days + unpaid_leave_days), 2))

    # 5. Calculate Earnings across effective salary structure segments (Pro-Rata)
    structure_segments = get_effective_salary_structures(db, tenant.id, student, start_date, end_date)

    earned_basic = 0.0
    earned_da = 0.0
    earned_hra = 0.0
    earned_conveyance = 0.0
    earned_medical = 0.0
    earned_special = 0.0
    earned_other = 0.0
    hourly_rate_applied = 0.0
    daily_rate_applied = 0.0
    primary_template_id = None
    primary_model = "STRUCTURED_SALARY"

    for seg_start, seg_end, st, seg_total_days in structure_segments:
        primary_template_id = st.template_id
        primary_model = st.compensation_model
        hourly_rate_applied = st.hourly_rate
        daily_rate_applied = st.daily_rate

        # Ratio of this segment to the full period
        seg_weight = seg_total_days / float(calendar_days_count) if calendar_days_count > 0 else 1.0
        seg_working_days = round(total_working_days * seg_weight, 2)

        # Attendance ratio for this segment
        att_ratio = min(1.0, (present_days_count + paid_leave_days) / max(1.0, total_working_days))

        if st.compensation_model == "STRUCTURED_SALARY":
            earned_basic += (st.monthly_basic * seg_weight) * att_ratio
            earned_da += (st.monthly_da * seg_weight) * att_ratio
            earned_hra += (st.monthly_hra * seg_weight) * att_ratio
            earned_conveyance += (st.conveyance_allowance * seg_weight) * att_ratio
            earned_medical += (st.medical_allowance * seg_weight) * att_ratio
            earned_special += (st.special_allowance * seg_weight) * att_ratio
            earned_other += (st.other_allowances * seg_weight) * att_ratio

        elif st.compensation_model == "MONTHLY_FIXED":
            m_gross = st.monthly_gross if st.monthly_gross > 0 else (student.monthly_base_salary or 35000.0)
            seg_gross = (m_gross * seg_weight) * att_ratio
            earned_basic += seg_gross * 0.60
            earned_hra += seg_gross * 0.20
            earned_special += seg_gross * 0.20

        elif st.compensation_model == "HOURLY":
            h_rate = st.hourly_rate if st.hourly_rate > 0 else (student.hourly_rate or 15.0)
            seg_hours = total_billed_hours * seg_weight
            earned_basic += seg_hours * h_rate

        elif st.compensation_model == "DAILY_WAGE":
            d_rate = st.daily_rate if st.daily_rate > 0 else (student.monthly_base_salary / 26.0 if student.monthly_base_salary else 500.0)
            seg_present = (present_days_count + paid_leave_days) * seg_weight
            earned_basic += seg_present * d_rate

        elif st.compensation_model == "STIPEND":
            stip = st.fixed_stipend if st.fixed_stipend > 0 else (student.monthly_base_salary or 15000.0)
            seg_stip = stip * seg_weight
            per_day_stip = seg_stip / max(1.0, seg_working_days)
            lwp_ded = per_day_stip * (unpaid_leave_days * seg_weight)
            earned_basic += max(0.0, seg_stip - lwp_ded)

        elif st.compensation_model in ("CONTRACT", "COMMISSION", "HYBRID"):
            m_gross = st.monthly_gross if st.monthly_gross > 0 else (student.monthly_base_salary or 30000.0)
            seg_base = (m_gross * seg_weight) * att_ratio
            earned_basic += seg_base * 0.70
            earned_special += seg_base * 0.30

    # 6. Compute Overtime Outlay
    effective_struct = structure_segments[-1][2]
    if effective_struct.compensation_model == "HOURLY":
        ot_base_rate = effective_struct.hourly_rate if effective_struct.hourly_rate > 0 else (student.hourly_rate or 15.0)
    else:
        monthly_denom = (earned_basic + earned_da) if (earned_basic + earned_da) > 0 else (student.monthly_base_salary or 35000.0)
        ot_base_rate = monthly_denom / max(1.0, total_working_days * std_daily_hours)

    reg_ot_pay = round(total_regular_ot_hours * ot_base_rate * ot_multiplier, 2)
    hol_ot_pay = round(total_holiday_ot_hours * ot_base_rate * holiday_ot_multiplier, 2)
    total_ot_earnings = round(reg_ot_pay + hol_ot_pay, 2)

    # 7. Gross Earnings Summary
    earned_basic = round(earned_basic, 2)
    earned_da = round(earned_da, 2)
    earned_hra = round(earned_hra, 2)
    earned_conveyance = round(earned_conveyance, 2)
    earned_medical = round(earned_medical, 2)
    earned_special = round(earned_special, 2)
    earned_other = round(earned_other, 2)

    total_gross = round(
        earned_basic + earned_da + earned_hra + earned_conveyance + earned_medical +
        earned_special + earned_other + total_ot_earnings + bonus_incentives,
        2
    )

    # 8. Statutory Deductions Engine (EPF, ESIC, PT, TDS)
    epf_ee = 0.0
    epf_er = 0.0
    eps_er = 0.0
    esic_ee = 0.0
    esic_er = 0.0
    pt_amount = 0.0
    tds_amount = float(effective_struct.tds_monthly_amount or 0.0)

    # A) EPF (Provident Fund)
    if effective_struct.enable_pf:
        pf_wage = earned_basic + earned_da
        if pf_wage > 0:
            if effective_struct.pf_capped_at_ceiling and branding and branding.enable_pf_ceiling:
                # Statutory ₹15,000 cap pro-rated by working days attendance
                ceiling = float(branding.epf_ceiling_limit or 15000.0)
                eligible_pf_wage = min(pf_wage, ceiling * min(1.0, (present_days_count + paid_leave_days) / max(1.0, total_working_days)))
            else:
                eligible_pf_wage = pf_wage

            ee_pct = float(branding.epf_employee_pct if branding and branding.epf_employee_pct is not None else 12.0) / 100.0
            er_pct = float(branding.epf_employer_pct if branding and branding.epf_employer_pct is not None else 12.0) / 100.0

            epf_ee = round(eligible_pf_wage * ee_pct, 2)
            # Employer 12% is split into EPS (8.33% up to ceiling) and EPF (3.67% + excess)
            eps_ceiling_wage = min(eligible_pf_wage, 15000.0)
            eps_er = round(eps_ceiling_wage * 0.0833, 2)
            epf_er = round(max(0.0, (eligible_pf_wage * er_pct) - eps_er), 2)

    # B) ESIC (State Insurance)
    if effective_struct.enable_esi and total_gross > 0:
        esi_thresh = float(branding.esi_gross_threshold if branding and branding.esi_gross_threshold is not None else 21000.0)
        # Normal monthly gross projection
        projected_monthly_gross = (total_gross / max(1.0, (present_days_count + paid_leave_days))) * total_working_days if (present_days_count + paid_leave_days) > 0 else total_gross

        if projected_monthly_gross <= esi_thresh or effective_struct.monthly_gross <= esi_thresh:
            ee_esi_pct = float(branding.esic_employee_pct if branding and branding.esic_employee_pct is not None else 0.75) / 100.0
            er_esi_pct = float(branding.esic_employer_pct if branding and branding.esic_employer_pct is not None else 3.25) / 100.0
            esic_ee = round(total_gross * ee_esi_pct, 2)
            esic_er = round(total_gross * er_esi_pct, 2)

    # C) Professional Tax (PT)
    if effective_struct.enable_pt and total_gross > 0:
        pt_default = float(effective_struct.pt_monthly_amount or (branding.pt_monthly_default if branding else 200.0) or 200.0)
        # Standard slab exemption check: Gross <= 7500 usually 0
        if total_gross <= 7500.0:
            pt_amount = 0.0
        else:
            pt_amount = pt_default

    # 9. Net Salary & Employer Total CTC Outlay
    total_deductions = round(
        epf_ee + esic_ee + pt_amount + tds_amount + advance_loan_deduction + other_deductions_manual,
        2
    )
    net_salary = round(max(0.0, total_gross - total_deductions), 2)
    employer_ctc_outlay = round(total_gross + epf_er + eps_er + esic_er, 2)

    breakdown = {
        "compensation_model": primary_model,
        "currency_symbol": currency,
        "calendar_days": calendar_days_count,
        "working_days": total_working_days,
        "present_days": present_days_count,
        "paid_leave_days": paid_leave_days,
        "unpaid_leave_days": unpaid_leave_days,
        "absent_days": absent_days_count,
        "billable_hours": total_billed_hours,
        "regular_ot_hours": total_regular_ot_hours,
        "holiday_ot_hours": total_holiday_ot_hours,
        "ot_base_rate": round(ot_base_rate, 2),
        "ot_multiplier": ot_multiplier,
        "holiday_ot_multiplier": holiday_ot_multiplier,
        "missed_checkouts": missed_checkouts,
        "late_checkins": late_checkins,
        "early_departures": early_departures,
        "earnings": {
            "basic": earned_basic,
            "da": earned_da,
            "hra": earned_hra,
            "conveyance": earned_conveyance,
            "medical": earned_medical,
            "special_allowance": earned_special,
            "other_allowances": earned_other,
            "overtime_regular": reg_ot_pay,
            "overtime_holiday": hol_ot_pay,
            "overtime_total": total_ot_earnings,
            "bonus_incentives": bonus_incentives,
            "gross_total": total_gross,
        },
        "deductions": {
            "epf_employee": epf_ee,
            "esic_employee": esic_ee,
            "professional_tax": pt_amount,
            "tds": tds_amount,
            "loan_advance": advance_loan_deduction,
            "other_manual": other_deductions_manual,
            "total_deductions": total_deductions,
        },
        "employer_contributions": {
            "epf_employer": epf_er,
            "eps_employer": eps_er,
            "esic_employer": esic_er,
            "total_employer_liability": round(epf_er + eps_er + esic_er, 2),
        },
        "net_payable": net_salary,
        "net_in_words": number_to_words_inr(net_salary),
        "employer_ctc_outlay": employer_ctc_outlay,
    }

    return {
        "student_id": student.id,
        "student_name": student.name,
        "roll_number": student.roll_number,
        "department_id": student.department_id,
        "department": student.department or (student.department_rel.name if student.department_rel else "General"),
        "designation": student.designation or (student.designation_rel.title if student.designation_rel else "Staff"),
        "template_id": primary_template_id,
        "compensation_model": primary_model,
        "calendar_days": calendar_days_count,
        "working_days": total_working_days,
        "present_days": present_days_count,
        "paid_leave_days": paid_leave_days,
        "unpaid_leave_days": unpaid_leave_days,
        "absent_days": absent_days_count,
        "billable_hours": total_billed_hours,
        "regular_ot_hours": total_regular_ot_hours,
        "holiday_ot_hours": total_holiday_ot_hours,
        "ot_earnings": total_ot_earnings,
        "basic_earned": earned_basic,
        "da_earned": earned_da,
        "hra_earned": earned_hra,
        "conveyance_earned": earned_conveyance,
        "medical_earned": earned_medical,
        "special_allowance_earned": earned_special,
        "other_earnings": earned_other,
        "incentives_bonus": bonus_incentives,
        "gross_earnings": total_gross,
        "epf_employee": epf_ee,
        "epf_employer": epf_er,
        "eps_employer": eps_er,
        "esic_employee": esic_ee,
        "esic_employer": esic_er,
        "professional_tax": pt_amount,
        "tds_deduction": tds_amount,
        "advance_loan_deduction": advance_loan_deduction,
        "other_deductions": other_deductions_manual,
        "total_deductions": total_deductions,
        "net_salary": net_salary,
        "employer_total_ctc_outlay": employer_ctc_outlay,
        "payment_method": payment_method,
        "remarks": remarks,
        "breakdown": breakdown,
    }
