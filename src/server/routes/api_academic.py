import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_

from src.database.models import (
    Tenant,
    User,
    Department,
    AcademicYear,
    ClassModel,
    Division,
    TeacherClassAssignment,
    Student,
    AuditLog,
)
from src.database.session import get_db
from src.server.tenant_middleware import get_current_tenant
from src.server.rbac_middleware import require_roles, get_current_user, check_tenant_operational_access
from src.utils.auth_utils import hash_password
from src.utils.timezone import get_ist_now

logger = logging.getLogger("api_academic")
router = APIRouter(
    prefix="/api/v1/academic",
    tags=["Academic Hierarchy & Progression"],
    dependencies=[Depends(require_roles(["TENANT_ADMIN"]))],
)


# --- Request & Response Schemas ---
class CreateDepartmentRequest(BaseModel):
    name: str
    code: Optional[str] = None
    description: Optional[str] = None


class UpdateDepartmentRequest(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None


class CreateAcademicYearRequest(BaseModel):
    name: str
    is_current: bool = True
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class CreateClassRequest(BaseModel):
    name: str
    department_id: Optional[int] = None
    department: Optional[str] = "Computer Science"
    code: Optional[str] = None


class UpdateClassRequest(BaseModel):
    name: Optional[str] = None
    department_id: Optional[int] = None
    department: Optional[str] = None
    code: Optional[str] = None


class CreateDivisionRequest(BaseModel):
    class_id: int
    name: str


class UpdateDivisionRequest(BaseModel):
    name: Optional[str] = None
    class_id: Optional[int] = None


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


# ==========================================================
# 1. DEPARTMENTS CRUD & REFERENTIAL INTEGRITY
# ==========================================================
@router.get("/departments")
def list_departments(
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    """Lists all academic departments for current tenant."""
    departments = (
        db.query(Department)
        .filter(Department.tenant_id == tenant.id)
        .order_by(Department.name.asc())
        .all()
    )
    return {"status": "success", "departments": [d.to_dict() for d in departments]}


@router.post("/departments")
def create_department(
    payload: CreateDepartmentRequest,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    """Creates a new institutional Department scoped to the active tenant."""
    check_tenant_operational_access(tenant)
    name_clean = payload.name.strip()
    if not name_clean:
        raise HTTPException(status_code=400, detail="Department name cannot be empty.")

    existing = db.query(Department).filter(
        Department.tenant_id == tenant.id,
        Department.name == name_clean,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Department '{name_clean}' already exists in this institution.")

    code_clean = payload.code.strip().upper() if payload.code else name_clean[:6].upper()
    dept = Department(
        tenant_id=tenant.id,
        name=name_clean,
        code=code_clean,
        description=payload.description.strip() if payload.description else "",
    )
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return {"status": "success", "message": f"Department '{name_clean}' created.", "department": dept.to_dict()}


@router.put("/departments/{department_id}")
def update_department(
    department_id: int,
    payload: UpdateDepartmentRequest,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    """Updates an existing department's name, code, and description."""
    check_tenant_operational_access(tenant)
    dept = db.query(Department).filter(
        Department.tenant_id == tenant.id,
        Department.id == department_id,
    ).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found.")

    if payload.name:
        name_clean = payload.name.strip()
        if name_clean != dept.name:
            dup = db.query(Department).filter(
                Department.tenant_id == tenant.id,
                Department.name == name_clean,
                Department.id != department_id,
            ).first()
            if dup:
                raise HTTPException(status_code=400, detail=f"Another department named '{name_clean}' already exists.")
            
            # Update matching legacy text references on classes and students
            db.query(ClassModel).filter(
                ClassModel.tenant_id == tenant.id,
                ClassModel.department_id == department_id,
            ).update({"department": name_clean})

            db.query(Student).filter(
                Student.tenant_id == tenant.id,
                Student.department_id == department_id,
            ).update({"department": name_clean})

            dept.name = name_clean

    if payload.code is not None:
        dept.code = payload.code.strip().upper()
    if payload.description is not None:
        dept.description = payload.description.strip()

    db.commit()
    db.refresh(dept)
    return {"status": "success", "message": f"Department '{dept.name}' updated.", "department": dept.to_dict()}


@router.delete("/departments/{department_id}")
def delete_department(
    department_id: int,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    """
    Deletes an empty department.
    Enforces strict referential integrity (RESTRICT): rejects deletion if active classes or students are linked.
    """
    check_tenant_operational_access(tenant)
    dept = db.query(Department).filter(
        Department.tenant_id == tenant.id,
        Department.id == department_id,
    ).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found.")

    classes_count = db.query(ClassModel).filter(
        ClassModel.tenant_id == tenant.id,
        or_(ClassModel.department_id == department_id, ClassModel.department == dept.name),
    ).count()

    students_count = db.query(Student).filter(
        Student.tenant_id == tenant.id,
        or_(Student.department_id == department_id, Student.department == dept.name),
    ).count()

    if classes_count > 0 or students_count > 0:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot delete Department '{dept.name}': It contains {classes_count} class(es) "
                f"and {students_count} student(s). Please reassign or delete these records first."
            ),
        )

    dept_name = dept.name
    db.delete(dept)
    db.commit()
    return {"status": "success", "message": f"Department '{dept_name}' deleted successfully."}


# ==========================================================
# 2. ACADEMIC YEARS
# ==========================================================
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
    check_tenant_operational_access(tenant)
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


# ==========================================================
# 3. CLASSES & REFERENTIAL INTEGRITY
# ==========================================================
@router.get("/classes")
def list_classes(
    department_id: Optional[int] = None,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    query = db.query(ClassModel).filter(ClassModel.tenant_id == tenant.id)
    if department_id:
        query = query.filter(ClassModel.department_id == department_id)
    classes = query.order_by(ClassModel.id.asc()).all()
    return {"status": "success", "classes": [c.to_dict() for c in classes]}


@router.post("/classes")
def create_class(
    payload: CreateClassRequest,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    check_tenant_operational_access(tenant)
    name_clean = payload.name.strip()
    existing = db.query(ClassModel).filter(ClassModel.tenant_id == tenant.id, ClassModel.name == name_clean).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Class '{name_clean}' already exists in this institution.")

    # Resolve department
    dept_id = payload.department_id
    dept_name = (payload.department or "Computer Science").strip()

    if dept_id:
        dept_obj = db.query(Department).filter(Department.tenant_id == tenant.id, Department.id == dept_id).first()
        if not dept_obj:
            raise HTTPException(status_code=404, detail="Selected department not found.")
        dept_name = dept_obj.name
    else:
        dept_obj = db.query(Department).filter(Department.tenant_id == tenant.id, Department.name == dept_name).first()
        if dept_obj:
            dept_id = dept_obj.id

    class_obj = ClassModel(
        tenant_id=tenant.id,
        department_id=dept_id,
        department=dept_name,
        name=name_clean,
        code=payload.code.strip() if payload.code else name_clean[:10].upper(),
    )
    db.add(class_obj)
    db.commit()
    db.refresh(class_obj)
    return {"status": "success", "message": f"Class '{name_clean}' created.", "class": class_obj.to_dict()}


@router.put("/classes/{class_id}")
def update_class(
    class_id: int,
    payload: UpdateClassRequest,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    """Updates class name, code, or department assignment."""
    check_tenant_operational_access(tenant)
    class_obj = db.query(ClassModel).filter(
        ClassModel.tenant_id == tenant.id,
        ClassModel.id == class_id,
    ).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="Class not found.")

    if payload.name:
        name_clean = payload.name.strip()
        if name_clean != class_obj.name:
            dup = db.query(ClassModel).filter(
                ClassModel.tenant_id == tenant.id,
                ClassModel.name == name_clean,
                ClassModel.id != class_id,
            ).first()
            if dup:
                raise HTTPException(status_code=400, detail=f"Another class named '{name_clean}' already exists.")
            class_obj.name = name_clean

    if payload.department_id:
        dept_obj = db.query(Department).filter(
            Department.tenant_id == tenant.id,
            Department.id == payload.department_id,
        ).first()
        if not dept_obj:
            raise HTTPException(status_code=404, detail="Selected department not found.")
        class_obj.department_id = dept_obj.id
        class_obj.department = dept_obj.name
    elif payload.department:
        dept_clean = payload.department.strip()
        dept_obj = db.query(Department).filter(
            Department.tenant_id == tenant.id,
            Department.name == dept_clean,
        ).first()
        if dept_obj:
            class_obj.department_id = dept_obj.id
            class_obj.department = dept_obj.name
        else:
            class_obj.department = dept_clean

    if payload.code is not None:
        class_obj.code = payload.code.strip()

    db.commit()
    db.refresh(class_obj)
    return {"status": "success", "message": f"Class '{class_obj.name}' updated.", "class": class_obj.to_dict()}


@router.delete("/classes/{class_id}")
def delete_class(
    class_id: int,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    """
    Deletes a class created by mistake.
    Enforces strict referential integrity (RESTRICT): rejects deletion if active students are assigned.
    """
    check_tenant_operational_access(tenant)
    class_obj = db.query(ClassModel).filter(
        ClassModel.tenant_id == tenant.id,
        ClassModel.id == class_id,
    ).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="Class not found.")

    students_count = db.query(Student).filter(
        Student.tenant_id == tenant.id,
        Student.class_id == class_id,
    ).count()

    if students_count > 0:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot delete Class '{class_obj.name}': It contains {students_count} enrolled student(s). "
                f"Please promote or reassign these students before deleting the class."
            ),
        )

    class_name = class_obj.name
    db.delete(class_obj)
    db.commit()
    return {"status": "success", "message": f"Class '{class_name}' and associated divisions deleted."}


# ==========================================================
# 4. DIVISIONS & REFERENTIAL INTEGRITY
# ==========================================================
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
    check_tenant_operational_access(tenant)
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


@router.put("/divisions/{division_id}")
def update_division(
    division_id: int,
    payload: UpdateDivisionRequest,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    """Updates division name or reassigns parent class."""
    check_tenant_operational_access(tenant)
    div = db.query(Division).filter(
        Division.tenant_id == tenant.id,
        Division.id == division_id,
    ).first()
    if not div:
        raise HTTPException(status_code=404, detail="Division not found.")

    if payload.name:
        name_clean = payload.name.strip()
        target_class_id = payload.class_id or div.class_id
        dup = db.query(Division).filter(
            Division.tenant_id == tenant.id,
            Division.class_id == target_class_id,
            Division.name == name_clean,
            Division.id != division_id,
        ).first()
        if dup:
            raise HTTPException(status_code=400, detail=f"Division '{name_clean}' already exists for this class.")
        div.name = name_clean

    if payload.class_id and payload.class_id != div.class_id:
        target_class = db.query(ClassModel).filter(
            ClassModel.tenant_id == tenant.id,
            ClassModel.id == payload.class_id,
        ).first()
        if not target_class:
            raise HTTPException(status_code=404, detail="Target parent class not found.")
        div.class_id = payload.class_id

    db.commit()
    db.refresh(div)
    return {"status": "success", "message": f"Division '{div.name}' updated.", "division": div.to_dict()}


@router.delete("/divisions/{division_id}")
def delete_division(
    division_id: int,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    """
    Deletes a division.
    Enforces strict referential integrity (RESTRICT): rejects deletion if students are assigned to this division.
    """
    check_tenant_operational_access(tenant)
    div = db.query(Division).filter(
        Division.tenant_id == tenant.id,
        Division.id == division_id,
    ).first()
    if not div:
        raise HTTPException(status_code=404, detail="Division not found.")

    students_count = db.query(Student).filter(
        Student.tenant_id == tenant.id,
        Student.division_id == division_id,
    ).count()

    if students_count > 0:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot delete Division '{div.name}': It contains {students_count} enrolled student(s). "
                f"Please reassign students to another division or parent class first."
            ),
        )

    div_name = div.name
    db.delete(div)
    db.commit()
    return {"status": "success", "message": f"Division '{div_name}' deleted successfully."}


# ==========================================================
# 5. TEACHERS & FACULTY ASSIGNMENTS
# ==========================================================
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
    check_tenant_operational_access(tenant)
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
    check_tenant_operational_access(tenant)
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
    check_tenant_operational_access(tenant)
    assignment = db.query(TeacherClassAssignment).filter(
        TeacherClassAssignment.tenant_id == tenant.id,
        TeacherClassAssignment.id == assignment_id,
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found.")

    db.delete(assignment)
    db.commit()
    return {"status": "success", "message": "Teacher assignment removed."}


# ==========================================================
# 6. FILTERED STUDENT DIRECTORY & PROMOTION COHORTS
# ==========================================================
@router.get("/students")
def list_cohort_students(
    department_id: Optional[int] = None,
    class_id: Optional[int] = None,
    division_id: Optional[int] = None,
    academic_year_id: Optional[int] = None,
    role: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    """
    Returns filtered student roster for academic progression, promotion engine, and directory.
    Eliminates infinite loading by supporting direct database query filters.
    """
    query = db.query(Student).filter(Student.tenant_id == tenant.id)

    if department_id:
        query = query.filter(Student.department_id == department_id)
    if class_id:
        query = query.filter(Student.class_id == class_id)
    if division_id:
        query = query.filter(Student.division_id == division_id)
    if academic_year_id:
        query = query.filter(Student.academic_year_id == academic_year_id)
    if role:
        query = query.filter(Student.user_role == role.strip().lower())
    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Student.name.ilike(search_term),
                Student.roll_number.ilike(search_term),
                Student.email.ilike(search_term),
            )
        )

    students = query.order_by(Student.roll_number.asc()).all()
    return {
        "status": "success",
        "students": [s.to_dict() for s in students],
        "count": len(students),
    }


# ==========================================================
# 7. STUDENT PROMOTION & ROLLBACK ENGINE
# ==========================================================
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
    check_tenant_operational_access(tenant)
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
    check_tenant_operational_access(tenant)
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
