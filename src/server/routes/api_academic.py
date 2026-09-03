import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.database.models import (
    Tenant,
    User,
    AcademicYear,
    ClassModel,
    Division,
    TeacherClassAssignment,
    Student,
    AuditLog,
)
from src.database.session import get_db
from src.server.tenant_middleware import get_current_tenant
from src.server.rbac_middleware import require_roles, get_current_user
from src.utils.auth_utils import hash_password
from src.utils.timezone import get_ist_now

logger = logging.getLogger("api_academic")
router = APIRouter(
    prefix="/api/v1/academic",
    tags=["Academic Hierarchy & Progression"],
    dependencies=[Depends(require_roles(["SUPER_ADMIN", "TENANT_ADMIN"]))],
)


# Request Schemas
class CreateAcademicYearRequest(BaseModel):
    name: str
    is_current: bool = True
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class CreateClassRequest(BaseModel):
    name: str
    department: str = "Computer Science"
    code: Optional[str] = None


class CreateDivisionRequest(BaseModel):
    class_id: int
    name: str


class CreateTeacherUserRequest(BaseModel):
    username: str
    email: str
    full_name: str
    password: str
    phone_number: Optional[str] = None


class AssignTeacherRequest(BaseModel):
    teacher_id: int
    class_id: int
    division_id: Optional[int] = None
    academic_year_id: Optional[int] = None
    subject: str = "General"


class StudentPromotionRequest(BaseModel):
    student_ids: List[int]
    target_class_id: int
    target_division_id: Optional[int] = None
    target_academic_year_id: Optional[int] = None


class PromotionRollbackRequest(BaseModel):
    student_ids: Optional[List[int]] = None
    class_id: Optional[int] = None  # Rollback whole class if specified


# --- Academic Years ---
@router.get("/years")
def list_academic_years(
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    years = db.query(AcademicYear).filter(AcademicYear.tenant_id == tenant.id).order_by(AcademicYear.id.desc()).all()
    return {"status": "success", "years": [y.to_dict() for y in years]}


@router.post("/years")
def create_academic_year(
    payload: CreateAcademicYearRequest,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    name_clean = payload.name.strip()
    if payload.is_current:
        # De-activate previous current years
        db.query(AcademicYear).filter(AcademicYear.tenant_id == tenant.id).update({"is_current": False})

    existing = db.query(AcademicYear).filter(AcademicYear.tenant_id == tenant.id, AcademicYear.name == name_clean).first()
    if existing:
        existing.is_current = payload.is_current
        db.commit()
        return {"status": "success", "message": f"Academic Year '{name_clean}' updated.", "year": existing.to_dict()}

    year = AcademicYear(
        tenant_id=tenant.id,
        name=name_clean,
        is_current=payload.is_current,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    db.add(year)
    db.commit()
    db.refresh(year)
    return {"status": "success", "message": f"Academic Year '{name_clean}' created.", "year": year.to_dict()}


# --- Classes ---
@router.get("/classes")
def list_classes(
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    classes = db.query(ClassModel).filter(ClassModel.tenant_id == tenant.id).order_by(ClassModel.id.asc()).all()
    return {"status": "success", "classes": [c.to_dict() for c in classes]}


@router.post("/classes")
def create_class(
    payload: CreateClassRequest,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    name_clean = payload.name.strip()
    existing = db.query(ClassModel).filter(ClassModel.tenant_id == tenant.id, ClassModel.name == name_clean).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Class '{name_clean}' already exists in this institution.")

    class_obj = ClassModel(
        tenant_id=tenant.id,
        department=payload.department.strip(),
        name=name_clean,
        code=payload.code.strip() if payload.code else name_clean[:10].upper(),
    )
    db.add(class_obj)
    db.commit()
    db.refresh(class_obj)
    return {"status": "success", "message": f"Class '{name_clean}' created.", "class": class_obj.to_dict()}


# --- Divisions ---
@router.get("/divisions")
def list_divisions(
    class_id: Optional[int] = None,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    query = db.query(Division).filter(Division.tenant_id == tenant.id)
    if class_id:
        query = query.filter(Division.class_id == class_id)
    divisions = query.order_by(Division.id.asc()).all()
    return {"status": "success", "divisions": [d.to_dict() for d in divisions]}


@router.post("/divisions")
def create_division(
    payload: CreateDivisionRequest,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    name_clean = payload.name.strip()
    class_obj = db.query(ClassModel).filter(ClassModel.tenant_id == tenant.id, ClassModel.id == payload.class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="Target class not found.")

    existing = db.query(Division).filter(
        Division.tenant_id == tenant.id,
        Division.class_id == payload.class_id,
        Division.name == name_clean,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Division '{name_clean}' already exists for {class_obj.name}.")

    div = Division(
        tenant_id=tenant.id,
        class_id=payload.class_id,
        name=name_clean,
    )
    db.add(div)
    db.commit()
    db.refresh(div)
    return {"status": "success", "message": f"Division '{name_clean}' created.", "division": div.to_dict()}


# --- Teachers & Faculty ---
@router.get("/teachers")
def list_teachers(
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    teachers = db.query(User).filter(User.tenant_id == tenant.id, User.role == "TEACHER").all()
    result = []
    for t in teachers:
        t_dict = t.to_dict()
        t_dict["assignments"] = [a.to_dict() for a in (t.teacher_assignments or [])]
        result.append(t_dict)
    return {"status": "success", "teachers": result}


@router.post("/teachers")
def create_teacher(
    payload: CreateTeacherUserRequest,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    username_clean = payload.username.strip().lower()
    existing = db.query(User).filter(User.tenant_id == tenant.id, User.username == username_clean).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Teacher username '{username_clean}' is already taken.")

    teacher = User(
        tenant_id=tenant.id,
        username=username_clean,
        email=payload.email.strip(),
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
        phone_number=payload.phone_number,
        role="TEACHER",
        is_active=True,
    )
    db.add(teacher)
    db.commit()
    db.refresh(teacher)
    return {"status": "success", "message": f"Teacher account '{teacher.full_name}' created.", "teacher": teacher.to_dict()}


# --- Teacher Assignments ---
@router.get("/teacher-assignments")
def list_teacher_assignments(
    teacher_id: Optional[int] = None,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    query = db.query(TeacherClassAssignment).filter(TeacherClassAssignment.tenant_id == tenant.id)
    if teacher_id:
        query = query.filter(TeacherClassAssignment.teacher_id == teacher_id)
    assignments = query.all()
    return {"status": "success", "assignments": [a.to_dict() for a in assignments]}


@router.post("/teacher-assignments")
def assign_teacher_to_class(
    payload: AssignTeacherRequest,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    teacher = db.query(User).filter(User.tenant_id == tenant.id, User.id == payload.teacher_id, User.role == "TEACHER").first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher user not found.")

    class_obj = db.query(ClassModel).filter(ClassModel.tenant_id == tenant.id, ClassModel.id == payload.class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="Target class not found.")

    assignment = TeacherClassAssignment(
        tenant_id=tenant.id,
        teacher_id=payload.teacher_id,
        class_id=payload.class_id,
        division_id=payload.division_id,
        academic_year_id=payload.academic_year_id,
        subject=payload.subject.strip(),
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return {"status": "success", "message": f"Assigned {teacher.full_name} to {class_obj.name}.", "assignment": assignment.to_dict()}


@router.delete("/teacher-assignments/{assignment_id}")
def remove_teacher_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    assignment = db.query(TeacherClassAssignment).filter(
        TeacherClassAssignment.tenant_id == tenant.id,
        TeacherClassAssignment.id == assignment_id,
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found.")

    db.delete(assignment)
    db.commit()
    return {"status": "success", "message": "Teacher assignment removed."}


# --- Student Progression & Downgrade / Rollback Engine ---
@router.post("/students/promote")
def promote_students_cohort(
    payload: StudentPromotionRequest,
    request: Request,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Promotes a batch of students to the next Class / Division / Academic Year.
    Stores previous class pointers to allow single-click rollback/downgrade if mistakes occur.
    Preserves all registered facial encodings and historical attendance records intact.
    """
    target_class = db.query(ClassModel).filter(ClassModel.tenant_id == tenant.id, ClassModel.id == payload.target_class_id).first()
    if not target_class:
        raise HTTPException(status_code=404, detail="Target class not found.")

    students = db.query(Student).filter(
        Student.tenant_id == tenant.id,
        Student.id.in_(payload.student_ids),
    ).all()

    if not students:
        raise HTTPException(status_code=400, detail="No valid students selected for promotion.")

    promoted_count = 0
    now_ist = get_ist_now()

    for s in students:
        # Save previous state for rollback
        s.previous_class_id = s.class_id
        s.previous_division_id = s.division_id
        s.previous_academic_year_id = s.academic_year_id
        s.last_promoted_at = now_ist

        # Apply new academic progression
        s.class_id = payload.target_class_id
        s.division_id = payload.target_division_id
        if payload.target_academic_year_id:
            s.academic_year_id = payload.target_academic_year_id
        s.class_semester = target_class.name
        promoted_count += 1

    # Record Audit Log
    audit = AuditLog(
        tenant_id=tenant.id,
        user_id=current_user.id,
        actor_name=current_user.full_name,
        actor_role=current_user.role,
        action_type="STUDENT_PROMOTION",
        target_type="CLASS",
        target_id=str(target_class.id),
        description=f"Promoted {promoted_count} students to '{target_class.name}'.",
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    db.commit()

    return {
        "status": "success",
        "message": f"Successfully promoted {promoted_count} student(s) to '{target_class.name}'.",
        "promoted_count": promoted_count,
        "target_class": target_class.name,
    }


@router.post("/students/rollback-promotion")
def rollback_student_promotion(
    payload: PromotionRollbackRequest,
    request: Request,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
):
    """
    Rolls back / downgrades a previously promoted batch or entire class back to their previous class state.
    """
    query = db.query(Student).filter(Student.tenant_id == tenant.id, Student.previous_class_id.isnot(None))

    if payload.student_ids:
        query = query.filter(Student.id.in_(payload.student_ids))
    elif payload.class_id:
        query = query.filter(Student.class_id == payload.class_id)
    else:
        raise HTTPException(status_code=400, detail="Must provide student_ids or class_id to execute rollback.")

    students = query.all()
    if not students:
        raise HTTPException(status_code=404, detail="No eligible students found with previous promotion history to rollback.")

    rollback_count = 0
    for s in students:
        prev_class_id = s.previous_class_id
        prev_div_id = s.previous_division_id
        prev_acad_id = s.previous_academic_year_id

        # Restore previous state
        prev_class_obj = db.query(ClassModel).filter(ClassModel.id == prev_class_id).first()
        s.class_id = prev_class_id
        s.division_id = prev_div_id
        s.academic_year_id = prev_acad_id
        s.class_semester = prev_class_obj.name if prev_class_obj else "General"

        # Clear previous markers
        s.previous_class_id = None
        s.previous_division_id = None
        s.previous_academic_year_id = None
        rollback_count += 1

    # Record Audit Log
    audit = AuditLog(
        tenant_id=tenant.id,
        user_id=current_user.id,
        actor_name=current_user.full_name,
        actor_role=current_user.role,
        action_type="PROMOTION_ROLLBACK",
        target_type="STUDENT_BATCH",
        target_id=str(rollback_count),
        description=f"Rolled back/downgraded promotion for {rollback_count} student(s) to previous academic cohort.",
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    db.commit()

    return {
        "status": "success",
        "message": f"Successfully rolled back/downgraded {rollback_count} student(s) to their prior classes.",
        "rollback_count": rollback_count,
    }
