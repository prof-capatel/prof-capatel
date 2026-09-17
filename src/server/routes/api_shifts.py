import re
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.database.models import WorkShift, Student, Tenant, AuditLog, User
from src.database.session import get_db
from src.server.tenant_middleware import get_current_tenant
from src.server.rbac_middleware import require_roles, check_tenant_operational_access, get_current_user_optional

logger = logging.getLogger("api_shifts")

router = APIRouter(
    prefix="/api/v1/shifts",
    tags=["Corporate Work Shifts Management"],
    dependencies=[Depends(require_roles(["SUPER_ADMIN", "TENANT_ADMIN"]))],
)

TIME_REGEX = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class ShiftCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    code: Optional[str] = Field(None, max_length=30)
    start_time: str = Field(..., description="24-hr time e.g. '09:00' or '10:30'")
    end_time: str = Field(..., description="24-hr time e.g. '17:30' or '18:00'")
    grace_period_minutes: Optional[int] = Field(15, ge=0, le=120)
    break_duration_minutes: Optional[int] = Field(0, ge=0, le=240)
    half_day_hours: Optional[float] = Field(4.0, ge=1.0, le=12.0)
    is_default: Optional[bool] = False

    @validator("start_time", "end_time")
    def validate_time_format(cls, v):
        v = v.strip()
        if not TIME_REGEX.match(v):
            raise ValueError("Time must be in 24-hour HH:MM format (e.g. 09:30, 18:00).")
        return v


class ShiftUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    code: Optional[str] = Field(None, max_length=30)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    grace_period_minutes: Optional[int] = Field(None, ge=0, le=120)
    break_duration_minutes: Optional[int] = Field(None, ge=0, le=240)
    half_day_hours: Optional[float] = Field(None, ge=1.0, le=12.0)
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None

    @validator("start_time", "end_time")
    def validate_time_format(cls, v):
        if v is not None:
            v = v.strip()
            if not TIME_REGEX.match(v):
                raise ValueError("Time must be in 24-hour HH:MM format (e.g. 09:30, 18:00).")
        return v


class BulkShiftAssignRequest(BaseModel):
    shift_id: int
    student_ids: List[int] = Field(..., min_items=1)


@router.get("")
def list_shifts(
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Lists all configured work shifts for the current corporate tenant."""
    shifts = (
        db.query(WorkShift)
        .filter(WorkShift.tenant_id == current_tenant.id)
        .order_by(WorkShift.is_default.desc(), WorkShift.name.asc())
        .all()
    )
    return {
        "status": "success",
        "tenant_id": current_tenant.id,
        "count": len(shifts),
        "shifts": [s.to_dict() for s in shifts],
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_shift(
    payload: ShiftCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Creates a new work shift for the tenant."""
    check_tenant_operational_access(current_tenant)
    clean_name = payload.name.strip()

    # Check for duplicate shift name in this tenant
    existing = (
        db.query(WorkShift)
        .filter(WorkShift.tenant_id == current_tenant.id, WorkShift.name == clean_name)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"A shift named '{clean_name}' already exists in this organization.",
        )

    # If first shift for this tenant, make it default automatically
    existing_count = db.query(WorkShift).filter(WorkShift.tenant_id == current_tenant.id).count()
    is_def = bool(payload.is_default) or (existing_count == 0)

    if is_def:
        # Reset other shifts to non-default
        db.query(WorkShift).filter(WorkShift.tenant_id == current_tenant.id).update({"is_default": False})

    clean_code = payload.code.strip().upper() if payload.code else clean_name[:4].upper()

    shift = WorkShift(
        tenant_id=current_tenant.id,
        name=clean_name,
        code=clean_code,
        start_time=payload.start_time,
        end_time=payload.end_time,
        grace_period_minutes=payload.grace_period_minutes if payload.grace_period_minutes is not None else 15,
        break_duration_minutes=payload.break_duration_minutes if payload.break_duration_minutes is not None else 0,
        half_day_hours=payload.half_day_hours if payload.half_day_hours is not None else 4.0,
        is_default=is_def,
        is_active=True,
    )
    db.add(shift)
    db.flush()

    if current_user:
        audit = AuditLog(
            tenant_id=current_tenant.id,
            user_id=current_user.id,
            actor_name=current_user.full_name,
            actor_role=current_user.role,
            action_type="SHIFT_CREATED",
            target_type="WORK_SHIFT",
            target_id=str(shift.id),
            description=f"Created work shift '{shift.name}' ({shift.start_time} - {shift.end_time}, Grace {shift.grace_period_minutes}m).",
            ip_address=request.client.host if request.client else None,
        )
        db.add(audit)

    db.commit()
    db.refresh(shift)

    logger.info(f"[+] Created work shift #{shift.id} '{shift.name}' for Tenant #{current_tenant.id}.")
    return {
        "status": "success",
        "message": f"Work shift '{shift.name}' created successfully.",
        "shift": shift.to_dict(),
    }


@router.get("/{shift_id}")
def get_shift(
    shift_id: int,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Fetches details of a single work shift."""
    shift = (
        db.query(WorkShift)
        .filter(WorkShift.tenant_id == current_tenant.id, WorkShift.id == shift_id)
        .first()
    )
    if not shift:
        raise HTTPException(status_code=404, detail="Work shift not found.")
    return {"status": "success", "shift": shift.to_dict()}


@router.put("/{shift_id}")
def update_shift(
    shift_id: int,
    payload: ShiftUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Updates an existing work shift's parameters."""
    check_tenant_operational_access(current_tenant)
    shift = (
        db.query(WorkShift)
        .filter(WorkShift.tenant_id == current_tenant.id, WorkShift.id == shift_id)
        .first()
    )
    if not shift:
        raise HTTPException(status_code=404, detail="Work shift not found.")

    if payload.name is not None:
        clean_name = payload.name.strip()
        existing = (
            db.query(WorkShift)
            .filter(
                WorkShift.tenant_id == current_tenant.id,
                WorkShift.name == clean_name,
                WorkShift.id != shift_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Another shift named '{clean_name}' already exists in this organization.",
            )
        shift.name = clean_name

    if payload.code is not None:
        shift.code = payload.code.strip().upper() if payload.code.strip() else shift.name[:4].upper()

    if payload.start_time is not None:
        shift.start_time = payload.start_time.strip()

    if payload.end_time is not None:
        shift.end_time = payload.end_time.strip()

    if payload.grace_period_minutes is not None:
        shift.grace_period_minutes = payload.grace_period_minutes

    if payload.break_duration_minutes is not None:
        shift.break_duration_minutes = payload.break_duration_minutes

    if payload.half_day_hours is not None:
        shift.half_day_hours = payload.half_day_hours

    if payload.is_active is not None:
        shift.is_active = payload.is_active

    if payload.is_default is True:
        db.query(WorkShift).filter(WorkShift.tenant_id == current_tenant.id).update({"is_default": False})
        shift.is_default = True
    elif payload.is_default is False and shift.is_default:
        # Cannot unset default shift unless another shift is default
        other_default = (
            db.query(WorkShift)
            .filter(WorkShift.tenant_id == current_tenant.id, WorkShift.id != shift_id, WorkShift.is_default == True)
            .first()
        )
        if not other_default:
            # Pick any other active shift to be default
            another = (
                db.query(WorkShift)
                .filter(WorkShift.tenant_id == current_tenant.id, WorkShift.id != shift_id)
                .first()
            )
            if another:
                another.is_default = True
                shift.is_default = False
            else:
                # Only 1 shift exists, must remain default
                shift.is_default = True

    if current_user:
        audit = AuditLog(
            tenant_id=current_tenant.id,
            user_id=current_user.id,
            actor_name=current_user.full_name,
            actor_role=current_user.role,
            action_type="SHIFT_UPDATED",
            target_type="WORK_SHIFT",
            target_id=str(shift.id),
            description=f"Updated shift '{shift.name}' ({shift.start_time} - {shift.end_time}).",
            ip_address=request.client.host if request.client else None,
        )
        db.add(audit)

    db.commit()
    db.refresh(shift)

    return {
        "status": "success",
        "message": f"Work shift '{shift.name}' updated successfully.",
        "shift": shift.to_dict(),
    }


@router.delete("/{shift_id}")
def delete_shift(
    shift_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Deletes a work shift.
    Safety constraint (User Choice 3A): Prevents deletion if active employees are currently assigned to this shift.
    """
    check_tenant_operational_access(current_tenant)
    shift = (
        db.query(WorkShift)
        .filter(WorkShift.tenant_id == current_tenant.id, WorkShift.id == shift_id)
        .first()
    )
    if not shift:
        raise HTTPException(status_code=404, detail="Work shift not found.")

    # Check for assigned employees
    assigned_count = (
        db.query(func.count(Student.id))
        .filter(Student.tenant_id == current_tenant.id, Student.shift_id == shift_id, Student.is_active == True)
        .scalar()
        or 0
    )
    if assigned_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete shift '{shift.name}': {assigned_count} active employee(s) are currently assigned to it. Please reassign their shifts first.",
        )

    # Check total shifts count
    total_shifts = db.query(WorkShift).filter(WorkShift.tenant_id == current_tenant.id).count()
    if total_shifts <= 1:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete the only work shift in this organization.",
        )

    was_default = shift.is_default
    shift_name = shift.name

    db.delete(shift)
    db.flush()

    # If deleted shift was default, make another shift default
    if was_default:
        next_shift = db.query(WorkShift).filter(WorkShift.tenant_id == current_tenant.id).first()
        if next_shift:
            next_shift.is_default = True

    if current_user:
        audit = AuditLog(
            tenant_id=current_tenant.id,
            user_id=current_user.id,
            actor_name=current_user.full_name,
            actor_role=current_user.role,
            action_type="SHIFT_DELETED",
            target_type="WORK_SHIFT",
            target_id=str(shift_id),
            description=f"Deleted work shift '{shift_name}'.",
            ip_address=request.client.host if request.client else None,
        )
        db.add(audit)

    db.commit()
    logger.info(f"[-] Deleted work shift #{shift_id} '{shift_name}' for Tenant #{current_tenant.id}.")
    return {
        "status": "success",
        "message": f"Work shift '{shift_name}' deleted successfully.",
    }


@router.post("/{shift_id}/set-default")
def set_default_shift(
    shift_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Sets a specific shift as the default fallback shift for the tenant."""
    check_tenant_operational_access(current_tenant)
    shift = (
        db.query(WorkShift)
        .filter(WorkShift.tenant_id == current_tenant.id, WorkShift.id == shift_id)
        .first()
    )
    if not shift:
        raise HTTPException(status_code=404, detail="Work shift not found.")

    db.query(WorkShift).filter(WorkShift.tenant_id == current_tenant.id).update({"is_default": False})
    shift.is_default = True

    if current_user:
        audit = AuditLog(
            tenant_id=current_tenant.id,
            user_id=current_user.id,
            actor_name=current_user.full_name,
            actor_role=current_user.role,
            action_type="SHIFT_SET_DEFAULT",
            target_type="WORK_SHIFT",
            target_id=str(shift.id),
            description=f"Designated '{shift.name}' as the default work shift.",
            ip_address=request.client.host if request.client else None,
        )
        db.add(audit)

    db.commit()
    db.refresh(shift)

    return {
        "status": "success",
        "message": f"'{shift.name}' is now the default work shift for this organization.",
        "shift": shift.to_dict(),
    }


@router.post("/bulk-assign")
def bulk_assign_shift(
    payload: BulkShiftAssignRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Bulk-assigns multiple employees to a selected work shift."""
    check_tenant_operational_access(current_tenant)
    shift = (
        db.query(WorkShift)
        .filter(WorkShift.tenant_id == current_tenant.id, WorkShift.id == payload.shift_id)
        .first()
    )
    if not shift:
        raise HTTPException(status_code=404, detail="Target work shift not found in this organization.")

    updated_count = (
        db.query(Student)
        .filter(
            Student.tenant_id == current_tenant.id,
            Student.id.in_(payload.student_ids),
        )
        .update({"shift_id": shift.id}, synchronize_session=False)
    )

    if current_user:
        audit = AuditLog(
            tenant_id=current_tenant.id,
            user_id=current_user.id,
            actor_name=current_user.full_name,
            actor_role=current_user.role,
            action_type="BULK_SHIFT_ASSIGNED",
            target_type="WORK_SHIFT",
            target_id=str(shift.id),
            description=f"Assigned {updated_count} employee(s) to shift '{shift.name}'.",
            ip_address=request.client.host if request.client else None,
        )
        db.add(audit)

    db.commit()

    return {
        "status": "success",
        "message": f"Successfully assigned {updated_count} employee(s) to '{shift.name}'.",
        "assigned_count": updated_count,
        "shift": shift.to_dict(),
    }
