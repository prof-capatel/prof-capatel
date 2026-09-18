from datetime import datetime
from pathlib import Path
from typing import List, Optional
import cv2
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_

from src.config import FACES_DIR
from src.core.camera_utils import decode_image_bytes, evaluate_image_quality
from src.core.face_engine import face_engine, FaceEngine
from src.database.models import (
    Student,
    FaceEncoding,
    Tenant,
    Department,
    ClassModel,
    Division,
    AcademicYear,
    AuditLog,
    User,
    WorkShift,
    CompanyLocation,
    DesignationMaster,
    SalaryTemplate,
    EmployeeSalaryStructure,
)
from src.database.session import get_db
from src.server.tenant_middleware import get_current_tenant
from src.server.rbac_middleware import check_tenant_operational_access, get_current_user_optional
from src.utils.timezone import get_ist_now

router = APIRouter(prefix="/api/v1/enroll", tags=["Student Enrollment"])


class StudentCreate(BaseModel):
    roll_number: str
    name: str
    department_id: Optional[int] = None
    department: Optional[str] = "Computer Science"
    class_id: Optional[int] = None
    division_id: Optional[int] = None
    academic_year_id: Optional[int] = None
    email: Optional[str] = None
    user_role: Optional[str] = None
    role: Optional[str] = None
    class_semester: Optional[str] = "General"
    hourly_rate: Optional[float] = None
    monthly_base_salary: Optional[float] = None
    shift_id: Optional[int] = None
    date_of_joining: Optional[str] = None
    location_id: Optional[int] = None
    designation_id: Optional[int] = None
    designation: Optional[str] = None
    salary_template_id: Optional[int] = None


class StudentUpdate(BaseModel):
    roll_number: str
    name: str
    department_id: Optional[int] = None
    department: Optional[str] = "Computer Science"
    class_id: Optional[int] = None
    division_id: Optional[int] = None
    academic_year_id: Optional[int] = None
    email: Optional[str] = None
    user_role: Optional[str] = None
    role: Optional[str] = None
    class_semester: Optional[str] = "General"
    hourly_rate: Optional[float] = None
    monthly_base_salary: Optional[float] = None
    shift_id: Optional[int] = None
    date_of_joining: Optional[str] = None
    location_id: Optional[int] = None
    designation_id: Optional[int] = None
    designation: Optional[str] = None
    salary_template_id: Optional[int] = None


class StudentDepartmentTransferPayload(BaseModel):
    department_id: int
    class_id: Optional[int] = None
    division_id: Optional[int] = None


class StudentRelievePayload(BaseModel):
    reason: Optional[str] = None
    relieving_reason: Optional[str] = None
    employment_status: Optional[str] = "RELIEVED"  # RELIEVED, TERMINATED, RESIGNED
    relieved_at: Optional[str] = None


class StudentReinstatePayload(BaseModel):
    reason: Optional[str] = "Reinstated to active employee roster"
    reinstating_reason: Optional[str] = None


@router.get("/students")
def list_enrolled_students(
    department_id: Optional[int] = None,
    class_id: Optional[int] = None,
    division_id: Optional[int] = None,
    academic_year_id: Optional[int] = None,
    user_role: Optional[str] = None,
    role: Optional[str] = None,
    shift_id: Optional[int] = None,
    status: Optional[str] = None,  # active, relieved, all
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """
    Lists enrolled students/employees with role, division, and status filtering.
    """
    query = db.query(Student).filter(Student.tenant_id == current_tenant.id)

    # Status Filtering
    if status:
        st_clean = status.strip().lower()
        if st_clean == "active":
            query = query.filter(Student.is_active == True)
        elif st_clean in ["relieved", "inactive"]:
            query = query.filter(or_(Student.is_active == False, Student.employment_status.in_(["RELIEVED", "TERMINATED", "RESIGNED"])))
        elif st_clean != "all":
            query = query.filter(Student.employment_status == status.strip().upper())

    if department_id:
        query = query.filter(Student.department_id == department_id)
    if class_id:
        query = query.filter(Student.class_id == class_id)
    if division_id:
        query = query.filter(Student.division_id == division_id)
    
    target_role = user_role or role
    if target_role:
        query = query.filter(Student.user_role == target_role.strip().lower())
    if shift_id:
        query = query.filter(Student.shift_id == shift_id)
    if search:
        search_clean = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Student.name.ilike(search_clean),
                Student.roll_number.ilike(search_clean),
                Student.email.ilike(search_clean),
            )
        )

    students = query.order_by(Student.name.asc()).all()
    return {
        "status": "success",
        "tenant_id": current_tenant.id,
        "students": [s.to_dict() for s in students],
        "count": len(students),
    }


@router.post("/student")
def register_student(
    payload: StudentCreate,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Registers a new student profile before capturing face samples scoped to current tenant."""
    check_tenant_operational_access(current_tenant)
    clean_roll = payload.roll_number.strip().upper()
    existing = db.query(Student).filter(
        Student.tenant_id == current_tenant.id,
        Student.roll_number == clean_roll,
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"User with Roll/ID Number '{clean_roll}' already exists in this institution.",
        )

    is_corporate = (getattr(current_tenant, "tenant_type", "educational") == "corporate")

    # Resolve Department
    default_dept = "General" if is_corporate else "Computer Science"
    dept_id = payload.department_id
    dept_name = (payload.department or default_dept).strip()
    if dept_id:
        dept_obj = db.query(Department).filter(Department.tenant_id == current_tenant.id, Department.id == dept_id).first()
        if dept_obj:
            dept_name = dept_obj.name
    else:
        dept_obj = db.query(Department).filter(Department.tenant_id == current_tenant.id, Department.name == dept_name).first()
        if dept_obj:
            dept_id = dept_obj.id

    # Resolve Class
    cls_id = payload.class_id
    cls_name = (payload.class_semester or ("Corporate" if is_corporate else "General")).strip()
    if cls_id:
        cls_obj = db.query(ClassModel).filter(ClassModel.tenant_id == current_tenant.id, ClassModel.id == cls_id).first()
        if cls_obj:
            cls_name = cls_obj.name
            if not dept_id and cls_obj.department_id:
                dept_id = cls_obj.department_id
                dept_name = cls_obj.department
    elif is_corporate:
        cls_id = None
        cls_name = "Corporate"

    # Resolve Division
    div_id = payload.division_id if not is_corporate else None
    if div_id:
        div_obj = db.query(Division).filter(Division.tenant_id == current_tenant.id, Division.id == div_id).first()
        if not div_obj:
            div_id = None

    # Resolve Academic Year
    acad_id = payload.academic_year_id if not is_corporate else None
    if not acad_id and not is_corporate:
        active_year = db.query(AcademicYear).filter(AcademicYear.tenant_id == current_tenant.id, AcademicYear.is_current == True).first()
        if active_year:
            acad_id = active_year.id

    # Resolve Default Role
    default_role = "employee" if is_corporate else "student"
    raw_role = payload.role or payload.user_role or default_role
    chosen_role = raw_role.strip().lower()
    if is_corporate and chosen_role == "student":
        chosen_role = "employee"

    # Resolve Date of Joining
    doj_val = None
    if payload.date_of_joining:
        try:
            doj_val = datetime.strptime(payload.date_of_joining.strip()[:10], "%Y-%m-%d").date()
        except Exception:
            pass
    if not doj_val and is_corporate:
        doj_val = get_ist_now().date()

    # Resolve Work Shift
    chosen_shift_id = payload.shift_id
    if chosen_shift_id:
        s_obj = db.query(WorkShift).filter(WorkShift.tenant_id == current_tenant.id, WorkShift.id == chosen_shift_id).first()
        if not s_obj:
            chosen_shift_id = None
    elif is_corporate:
        def_shift = db.query(WorkShift).filter(WorkShift.tenant_id == current_tenant.id, WorkShift.is_default == True).first()
        if def_shift:
            chosen_shift_id = def_shift.id
        else:
            any_shift = db.query(WorkShift).filter(WorkShift.tenant_id == current_tenant.id).first()
            if any_shift:
                chosen_shift_id = any_shift.id

    # Resolve Location
    loc_id = payload.location_id
    if loc_id:
        loc_obj = db.query(CompanyLocation).filter(CompanyLocation.tenant_id == current_tenant.id, CompanyLocation.id == loc_id).first()
        if not loc_obj:
            loc_id = None

    # Resolve Designation
    desig_id = payload.designation_id
    desig_title = payload.designation
    desig_obj = None
    if desig_id:
        desig_obj = db.query(DesignationMaster).filter(DesignationMaster.tenant_id == current_tenant.id, DesignationMaster.id == desig_id).first()
        if desig_obj:
            desig_title = desig_obj.title
        else:
            desig_id = None

    # Resolve Salary Template (explicit > designation)
    target_tpl_id = payload.salary_template_id
    if not target_tpl_id and desig_obj and getattr(desig_obj, "salary_template_id", None):
        target_tpl_id = desig_obj.salary_template_id

    student = Student(
        tenant_id=current_tenant.id,
        roll_number=clean_roll,
        name=payload.name.strip(),
        department_id=dept_id,
        department=dept_name,
        class_id=cls_id,
        class_semester=cls_name,
        division_id=div_id,
        academic_year_id=acad_id,
        email=payload.email.strip() if payload.email else None,
        user_role=chosen_role,
        hourly_rate=payload.hourly_rate,
        monthly_base_salary=payload.monthly_base_salary,
        shift_id=chosen_shift_id,
        date_of_joining=doj_val,
        location_id=loc_id,
        designation_id=desig_id,
        designation=desig_title,
    )
    db.add(student)
    db.flush()

    if is_corporate and target_tpl_id:
        tpl = db.query(SalaryTemplate).filter(SalaryTemplate.id == target_tpl_id, SalaryTemplate.tenant_id == current_tenant.id).first()
        if tpl:
            gross_val = float(payload.monthly_base_salary or 0.0)
            hr_val = float(payload.hourly_rate or 0.0)
            model_val = tpl.compensation_model

            if model_val == "STRUCTURED_SALARY" and gross_val > 0:
                basic_val = round(gross_val * (tpl.basic_percentage / 100.0), 2)
                da_val = round(gross_val * (tpl.da_percentage / 100.0), 2)
                hra_val = round(basic_val * (tpl.hra_percentage / 100.0), 2)
                conv_allow = tpl.conveyance_fixed
                med_allow = tpl.medical_fixed
                specified = basic_val + da_val + hra_val + conv_allow + med_allow
                special_allow = max(0.0, round(gross_val - specified, 2))
            else:
                basic_val = round(gross_val * 0.50, 2) if gross_val > 0 else 0.0
                da_val = 0.0
                hra_val = 0.0
                conv_allow = 0.0
                med_allow = 0.0
                special_allow = 0.0

            init_struct = EmployeeSalaryStructure(
                tenant_id=current_tenant.id,
                student_id=student.id,
                template_id=tpl.id,
                compensation_model=model_val,
                annual_ctc=gross_val * 12.0,
                monthly_gross=gross_val,
                monthly_basic=basic_val,
                monthly_da=da_val,
                monthly_hra=hra_val,
                conveyance_allowance=conv_allow,
                medical_allowance=med_allow,
                special_allowance=special_allow,
                other_allowances=0.0,
                hourly_rate=hr_val if hr_val > 0 else (round(gross_val / (26.0 * 8.0), 2) if gross_val > 0 else 0.0),
                daily_rate=round(gross_val / 26.0, 2) if gross_val > 0 else 0.0,
                fixed_stipend=gross_val if model_val == "STIPEND" else 0.0,
                enable_pf=tpl.enable_pf,
                pf_capped_at_ceiling=tpl.pf_capped_at_ceiling,
                enable_esi=tpl.enable_esi,
                enable_pt=tpl.enable_pt,
                effective_from_date=doj_val or get_ist_now().date(),
                effective_to_date=None,
                is_current=True,
                revision_reason="Initial Placement / Onboarding",
            )
            db.add(init_struct)

    db.commit()
    db.refresh(student)

    return {
        "status": "success",
        "tenant_id": current_tenant.id,
        "message": f"Profile '{student.name}' ({student.user_role}) registered successfully.",
        "student": student.to_dict(),
    }


@router.post("/capture-sample")
async def capture_face_sample(
    student_id: int = Form(...),
    sample_angle: str = Form("frontal"),  # frontal, left, right
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """
    Validates, extracts 128-d facial vector from uploaded frame,
    persists sample to MySQL and disk, and refreshes the tenant's in-memory FaceEngine cache.
    """
    check_tenant_operational_access(current_tenant)
    student = db.query(Student).filter(
        Student.id == student_id,
        Student.tenant_id == current_tenant.id,
    ).first()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found in this institution.")

    # Read image
    contents = await image.read()
    image_bgr = decode_image_bytes(contents)
    if image_bgr is None:
        raise HTTPException(status_code=400, detail="Invalid image uploaded.")

    # Evaluate image quality (brightness, blur)
    is_good_quality, quality_msg = evaluate_image_quality(image_bgr)
    if not is_good_quality:
        raise HTTPException(status_code=400, detail=f"Image quality check failed: {quality_msg}")

    # Extract 128-d vector and face bounding box
    vector, face_box, msg = FaceEngine.compute_single_face_vector(image_bgr)
    if vector is None:
        raise HTTPException(status_code=400, detail=msg)

    # Crop and save reference face image
    top, right, bottom, left = face_box
    h, w = image_bgr.shape[:2]
    pad_h = int((bottom - top) * 0.15)
    pad_w = int((right - left) * 0.15)
    crop = image_bgr[
        max(0, top - pad_h): min(h, bottom + pad_h),
        max(0, left - pad_w): min(w, right + pad_w),
    ]

    timestamp_str = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    clean_roll = student.roll_number.replace("/", "_").replace("\\", "_")
    filename = f"t{current_tenant.id}_student_{clean_roll}_{sample_angle}_{timestamp_str}.jpg"
    target_path = FACES_DIR / filename
    cv2.imwrite(str(target_path), crop, [cv2.IMWRITE_JPEG_QUALITY, 92])

    rel_path = f"faces/{filename}"

    # Remove previous sample with the same angle if updating
    existing_sample = (
        db.query(FaceEncoding)
        .filter(
            FaceEncoding.tenant_id == current_tenant.id,
            FaceEncoding.student_id == student.id,
            FaceEncoding.sample_angle == sample_angle,
        )
        .first()
    )
    if existing_sample:
        existing_sample.vector_json = FaceEncoding.from_numpy(
            student_id=student.id,
            vector=vector,
            sample_angle=sample_angle,
            photo_path=rel_path,
            tenant_id=current_tenant.id,
        ).vector_json
        existing_sample.photo_path = rel_path
    else:
        encoding_record = FaceEncoding.from_numpy(
            student_id=student.id,
            vector=vector,
            sample_angle=sample_angle,
            photo_path=rel_path,
            tenant_id=current_tenant.id,
        )
        db.add(encoding_record)

    db.commit()

    # Hot-reload in-memory vector cache for this tenant
    face_engine.reload_cache(db, tenant_id=current_tenant.id)

    total_samples = db.query(FaceEncoding).filter(
        FaceEncoding.tenant_id == current_tenant.id,
        FaceEncoding.student_id == student.id,
    ).count()

    return {
        "status": "success",
        "tenant_id": current_tenant.id,
        "message": f"Sample '{sample_angle}' recorded successfully.",
        "sample_angle": sample_angle,
        "total_samples": total_samples,
        "is_complete": total_samples >= 3,
        "photo_url": f"/data/{rel_path}",
    }


@router.post("/batch-upload")
async def batch_upload_enrollment(
    name: str = Form(...),
    roll_number: str = Form(...),
    department_id: Optional[int] = Form(None),
    department: str = Form("Computer Science"),
    class_id: Optional[int] = Form(None),
    division_id: Optional[int] = Form(None),
    academic_year_id: Optional[int] = Form(None),
    email: Optional[str] = Form(None),
    user_role: str = Form("student"),
    class_semester: Optional[str] = Form("General"),
    hourly_rate: Optional[float] = Form(None),
    monthly_base_salary: Optional[float] = Form(None),
    shift_id: Optional[int] = Form(None),
    date_of_joining: Optional[str] = Form(None),
    location_id: Optional[int] = Form(None),
    designation_id: Optional[int] = Form(None),
    designation: Optional[str] = Form(None),
    salary_template_id: Optional[int] = Form(None),
    photo_front: UploadFile = File(...),
    photo_left: UploadFile = File(...),
    photo_right: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """
    All-in-one 3-photo batch enrollment: creates student profile with referential links,
    processes 3 photos, extracts vectors, and hot-reloads vector memory cache for current tenant.
    """
    check_tenant_operational_access(current_tenant)
    clean_roll = roll_number.strip().upper()

    # Check duplicate
    existing = db.query(Student).filter(
        Student.tenant_id == current_tenant.id,
        Student.roll_number == clean_roll,
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"User with ID / Roll '{clean_roll}' already exists in this institution.",
        )

    is_corporate = (getattr(current_tenant, "tenant_type", "educational") == "corporate")

    # Resolve Department
    default_dept = "General" if is_corporate else "Computer Science"
    dept_id = department_id
    dept_name = (department or default_dept).strip()
    if dept_id:
        dept_obj = db.query(Department).filter(Department.tenant_id == current_tenant.id, Department.id == dept_id).first()
        if dept_obj:
            dept_name = dept_obj.name
    else:
        dept_obj = db.query(Department).filter(Department.tenant_id == current_tenant.id, Department.name == dept_name).first()
        if dept_obj:
            dept_id = dept_obj.id

    # Resolve Class
    cls_id = class_id
    cls_name = (class_semester or ("Corporate" if is_corporate else "General")).strip()
    if cls_id:
        cls_obj = db.query(ClassModel).filter(ClassModel.tenant_id == current_tenant.id, ClassModel.id == cls_id).first()
        if cls_obj:
            cls_name = cls_obj.name
            if not dept_id and cls_obj.department_id:
                dept_id = cls_obj.department_id
                dept_name = cls_obj.department
    elif is_corporate:
        cls_id = None
        cls_name = "Corporate"

    # Resolve Division
    div_id = division_id if not is_corporate else None
    if div_id:
        div_obj = db.query(Division).filter(Division.tenant_id == current_tenant.id, Division.id == div_id).first()
        if not div_obj:
            div_id = None

    # Resolve Academic Year
    acad_id = academic_year_id if not is_corporate else None
    if not acad_id and not is_corporate:
        active_year = db.query(AcademicYear).filter(AcademicYear.tenant_id == current_tenant.id, AcademicYear.is_current == True).first()
        if active_year:
            acad_id = active_year.id

    # Resolve Role
    default_role = "employee" if is_corporate else "student"
    chosen_role = user_role.strip().lower() if user_role else default_role
    if is_corporate and chosen_role == "student":
        chosen_role = "employee"

    # Process all 3 photos
    photos = [
        ("frontal", photo_front),
        ("left", photo_left),
        ("right", photo_right),
    ]

    processed_samples = []

    for angle, photo_file in photos:
        contents = await photo_file.read()
        image_bgr = decode_image_bytes(contents)
        if image_bgr is None:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid image file uploaded for {angle} angle.",
            )

        is_good_quality, quality_msg = evaluate_image_quality(image_bgr)
        if not is_good_quality:
            raise HTTPException(
                status_code=400,
                detail=f"Quality check failed for {angle} photo: {quality_msg}",
            )

        vector, face_box, msg = FaceEngine.compute_single_face_vector(image_bgr)
        if vector is None:
            raise HTTPException(
                status_code=400,
                detail=f"Face detection failed for {angle} angle photo: {msg}",
            )

        # Crop face
        top, right, bottom, left = face_box
        h, w = image_bgr.shape[:2]
        pad_h = int((bottom - top) * 0.15)
        pad_w = int((right - left) * 0.15)
        crop = image_bgr[
            max(0, top - pad_h): min(h, bottom + pad_h),
            max(0, left - pad_w): min(w, right + pad_w),
        ]

        timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        safe_roll = clean_roll.replace("/", "_").replace("\\", "_")
        filename = f"t{current_tenant.id}_batch_{safe_roll}_{angle}_{timestamp_str}.jpg"
        target_path = FACES_DIR / filename
        cv2.imwrite(str(target_path), crop, [cv2.IMWRITE_JPEG_QUALITY, 92])

        processed_samples.append({
            "angle": angle,
            "vector": vector,
            "rel_path": f"faces/{filename}",
        })

    # Resolve Date of Joining
    doj_val = None
    if date_of_joining:
        try:
            doj_val = datetime.strptime(date_of_joining.strip()[:10], "%Y-%m-%d").date()
        except Exception:
            pass
    if not doj_val and is_corporate:
        doj_val = get_ist_now().date()

    # Resolve Work Shift
    chosen_shift_id = shift_id
    if chosen_shift_id:
        s_obj = db.query(WorkShift).filter(WorkShift.tenant_id == current_tenant.id, WorkShift.id == chosen_shift_id).first()
        if not s_obj:
            chosen_shift_id = None
    elif is_corporate:
        def_shift = db.query(WorkShift).filter(WorkShift.tenant_id == current_tenant.id, WorkShift.is_default == True).first()
        if def_shift:
            chosen_shift_id = def_shift.id
        else:
            any_shift = db.query(WorkShift).filter(WorkShift.tenant_id == current_tenant.id).first()
            if any_shift:
                chosen_shift_id = any_shift.id

    # Resolve Location
    loc_id = location_id
    if loc_id:
        loc_obj = db.query(CompanyLocation).filter(CompanyLocation.tenant_id == current_tenant.id, CompanyLocation.id == loc_id).first()
        if not loc_obj:
            loc_id = None

    # Resolve Designation
    desig_id = designation_id
    desig_title = designation
    desig_obj = None
    if desig_id:
        desig_obj = db.query(DesignationMaster).filter(DesignationMaster.tenant_id == current_tenant.id, DesignationMaster.id == desig_id).first()
        if desig_obj:
            desig_title = desig_obj.title
        else:
            desig_id = None

    # Resolve Salary Template (explicit > designation)
    target_tpl_id = salary_template_id
    if not target_tpl_id and desig_obj and getattr(desig_obj, "salary_template_id", None):
        target_tpl_id = desig_obj.salary_template_id

    # Save Student
    student = Student(
        tenant_id=current_tenant.id,
        roll_number=clean_roll,
        name=name.strip(),
        department_id=dept_id,
        department=dept_name,
        class_id=cls_id,
        class_semester=cls_name,
        division_id=div_id,
        academic_year_id=acad_id,
        email=email.strip() if email else None,
        user_role=chosen_role,
        hourly_rate=hourly_rate,
        monthly_base_salary=monthly_base_salary,
        shift_id=chosen_shift_id,
        date_of_joining=doj_val,
        location_id=loc_id,
        designation_id=desig_id,
        designation=desig_title,
    )
    db.add(student)
    db.flush()

    # Save Face Encodings
    for sample in processed_samples:
        encoding_record = FaceEncoding.from_numpy(
            student_id=student.id,
            vector=sample["vector"],
            sample_angle=sample["angle"],
            photo_path=sample["rel_path"],
            tenant_id=current_tenant.id,
        )
        db.add(encoding_record)

    if is_corporate and target_tpl_id:
        tpl = db.query(SalaryTemplate).filter(SalaryTemplate.id == target_tpl_id, SalaryTemplate.tenant_id == current_tenant.id).first()
        if tpl:
            gross_val = float(monthly_base_salary or 0.0)
            hr_val = float(hourly_rate or 0.0)
            model_val = tpl.compensation_model

            if model_val == "STRUCTURED_SALARY" and gross_val > 0:
                basic_val = round(gross_val * (tpl.basic_percentage / 100.0), 2)
                da_val = round(gross_val * (tpl.da_percentage / 100.0), 2)
                hra_val = round(basic_val * (tpl.hra_percentage / 100.0), 2)
                conv_allow = tpl.conveyance_fixed
                med_allow = tpl.medical_fixed
                specified = basic_val + da_val + hra_val + conv_allow + med_allow
                special_allow = max(0.0, round(gross_val - specified, 2))
            else:
                basic_val = round(gross_val * 0.50, 2) if gross_val > 0 else 0.0
                da_val = 0.0
                hra_val = 0.0
                conv_allow = 0.0
                med_allow = 0.0
                special_allow = 0.0

            init_struct = EmployeeSalaryStructure(
                tenant_id=current_tenant.id,
                student_id=student.id,
                template_id=tpl.id,
                compensation_model=model_val,
                annual_ctc=gross_val * 12.0,
                monthly_gross=gross_val,
                monthly_basic=basic_val,
                monthly_da=da_val,
                monthly_hra=hra_val,
                conveyance_allowance=conv_allow,
                medical_allowance=med_allow,
                special_allowance=special_allow,
                other_allowances=0.0,
                hourly_rate=hr_val if hr_val > 0 else (round(gross_val / (26.0 * 8.0), 2) if gross_val > 0 else 0.0),
                daily_rate=round(gross_val / 26.0, 2) if gross_val > 0 else 0.0,
                fixed_stipend=gross_val if model_val == "STIPEND" else 0.0,
                enable_pf=tpl.enable_pf,
                pf_capped_at_ceiling=tpl.pf_capped_at_ceiling,
                enable_esi=tpl.enable_esi,
                enable_pt=tpl.enable_pt,
                effective_from_date=doj_val or get_ist_now().date(),
                effective_to_date=None,
                is_current=True,
                revision_reason="Initial Placement / Corporate Batch Onboarding",
            )
            db.add(init_struct)

    db.commit()
    db.refresh(student)

    # Hot-reload in-memory vector cache for this tenant
    face_engine.reload_cache(db, tenant_id=current_tenant.id)

    return {
        "status": "success",
        "tenant_id": current_tenant.id,
        "message": f"Successfully enrolled '{student.name}' ({student.user_role}) with all 3 biometric sample angles.",
        "student": student.to_dict(),
    }


@router.put("/student/{student_id}")
def update_student_profile(
    student_id: int,
    payload: StudentUpdate,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Updates an existing student/staff profile information within the tenant."""
    check_tenant_operational_access(current_tenant)
    student = db.query(Student).filter(
        Student.id == student_id,
        Student.tenant_id == current_tenant.id,
    ).first()

    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found in this institution.")

    clean_roll = payload.roll_number.strip().upper()
    existing_roll = (
        db.query(Student)
        .filter(
            Student.tenant_id == current_tenant.id,
            Student.roll_number == clean_roll,
            Student.id != student_id,
        )
        .first()
    )
    if existing_roll:
        raise HTTPException(
            status_code=400,
            detail=f"Roll Number / ID '{clean_roll}' is already assigned to another user in this institute.",
        )

    # Resolve Department
    dept_id = payload.department_id
    dept_name = (payload.department or "Computer Science").strip()
    if dept_id:
        dept_obj = db.query(Department).filter(Department.tenant_id == current_tenant.id, Department.id == dept_id).first()
        if dept_obj:
            dept_name = dept_obj.name
    elif payload.department:
        dept_obj = db.query(Department).filter(Department.tenant_id == current_tenant.id, Department.name == dept_name).first()
        if dept_obj:
            dept_id = dept_obj.id

    # Resolve Class
    cls_id = payload.class_id
    cls_name = (payload.class_semester or "General").strip()
    if cls_id:
        cls_obj = db.query(ClassModel).filter(ClassModel.tenant_id == current_tenant.id, ClassModel.id == cls_id).first()
        if cls_obj:
            cls_name = cls_obj.name

    # Resolve Division
    div_id = payload.division_id

    student.roll_number = clean_roll
    student.name = payload.name.strip()
    student.department_id = dept_id
    student.department = dept_name
    student.class_id = cls_id
    student.class_semester = cls_name
    student.division_id = div_id
    if payload.academic_year_id:
        student.academic_year_id = payload.academic_year_id
    student.email = payload.email.strip() if payload.email else None
    student.user_role = payload.user_role.strip().lower() if payload.user_role else "student"
    if payload.hourly_rate is not None:
        student.hourly_rate = payload.hourly_rate
    if payload.monthly_base_salary is not None:
        student.monthly_base_salary = payload.monthly_base_salary
    if payload.shift_id is not None:
        if payload.shift_id > 0:
            s_obj = db.query(WorkShift).filter(WorkShift.tenant_id == current_tenant.id, WorkShift.id == payload.shift_id).first()
            if s_obj:
                student.shift_id = s_obj.id
        else:
            student.shift_id = None
    if payload.date_of_joining is not None:
        if payload.date_of_joining.strip():
            try:
                student.date_of_joining = datetime.strptime(payload.date_of_joining.strip()[:10], "%Y-%m-%d").date()
            except Exception:
                pass
        else:
            student.date_of_joining = None

    fields_set = getattr(payload, "model_fields_set", getattr(payload, "__fields_set__", set()))

    if "location_id" in fields_set:
        if payload.location_id and payload.location_id > 0:
            loc_obj = db.query(CompanyLocation).filter(CompanyLocation.tenant_id == current_tenant.id, CompanyLocation.id == payload.location_id).first()
            student.location_id = loc_obj.id if loc_obj else None
        else:
            student.location_id = None

    if "designation_id" in fields_set:
        if payload.designation_id and payload.designation_id > 0:
            desig_obj = db.query(DesignationMaster).filter(DesignationMaster.tenant_id == current_tenant.id, DesignationMaster.id == payload.designation_id).first()
            if desig_obj:
                student.designation_id = desig_obj.id
                student.designation = desig_obj.title
            else:
                student.designation_id = None
                student.designation = None
        else:
            student.designation_id = None
            student.designation = None

    if "designation" in fields_set and payload.designation is not None:
        student.designation = payload.designation.strip()

    is_corporate = (getattr(current_tenant, "tenant_type", "educational") == "corporate")
    if is_corporate and ("salary_template_id" in fields_set or "designation_id" in fields_set or "monthly_base_salary" in fields_set or "hourly_rate" in fields_set):
        target_tpl_id = payload.salary_template_id
        if not target_tpl_id and "salary_template_id" not in fields_set:
            if student.designation_id:
                des_obj = db.query(DesignationMaster).filter(DesignationMaster.id == student.designation_id, DesignationMaster.tenant_id == current_tenant.id).first()
                if des_obj and des_obj.salary_template_id:
                    target_tpl_id = des_obj.salary_template_id
            if not target_tpl_id:
                existing_curr = db.query(EmployeeSalaryStructure).filter(
                    EmployeeSalaryStructure.tenant_id == current_tenant.id,
                    EmployeeSalaryStructure.student_id == student.id,
                    EmployeeSalaryStructure.is_current == True,
                ).first()
                if existing_curr:
                    target_tpl_id = existing_curr.template_id

        if target_tpl_id and target_tpl_id > 0:
            tpl = db.query(SalaryTemplate).filter(SalaryTemplate.id == target_tpl_id, SalaryTemplate.tenant_id == current_tenant.id).first()
            if tpl:
                gross_val = float(student.monthly_base_salary or 0.0)
                hr_val = float(student.hourly_rate or 0.0)
                model_val = tpl.compensation_model

                if model_val == "STRUCTURED_SALARY" and gross_val > 0:
                    basic_val = round(gross_val * (tpl.basic_percentage / 100.0), 2)
                    da_val = round(gross_val * (tpl.da_percentage / 100.0), 2)
                    hra_val = round(basic_val * (tpl.hra_percentage / 100.0), 2)
                    conv_allow = tpl.conveyance_fixed
                    med_allow = tpl.medical_fixed
                    specified = basic_val + da_val + hra_val + conv_allow + med_allow
                    special_allow = max(0.0, round(gross_val - specified, 2))
                else:
                    basic_val = round(gross_val * 0.50, 2) if gross_val > 0 else 0.0
                    da_val = 0.0
                    hra_val = 0.0
                    conv_allow = 0.0
                    med_allow = 0.0
                    special_allow = 0.0

                existing_struct = db.query(EmployeeSalaryStructure).filter(
                    EmployeeSalaryStructure.tenant_id == current_tenant.id,
                    EmployeeSalaryStructure.student_id == student.id,
                    EmployeeSalaryStructure.is_current == True,
                ).first()

                eff_from = get_ist_now().date()
                if existing_struct:
                    existing_struct.is_current = False
                    if not existing_struct.effective_to_date or existing_struct.effective_to_date >= eff_from:
                        existing_struct.effective_to_date = eff_from

                new_struct = EmployeeSalaryStructure(
                    tenant_id=current_tenant.id,
                    student_id=student.id,
                    template_id=tpl.id,
                    compensation_model=model_val,
                    annual_ctc=gross_val * 12.0,
                    monthly_gross=gross_val,
                    monthly_basic=basic_val,
                    monthly_da=da_val,
                    monthly_hra=hra_val,
                    conveyance_allowance=conv_allow,
                    medical_allowance=med_allow,
                    special_allowance=special_allow,
                    other_allowances=0.0,
                    hourly_rate=hr_val if hr_val > 0 else (round(gross_val / (26.0 * 8.0), 2) if gross_val > 0 else 0.0),
                    daily_rate=round(gross_val / 26.0, 2) if gross_val > 0 else 0.0,
                    fixed_stipend=gross_val if model_val == "STIPEND" else 0.0,
                    enable_pf=tpl.enable_pf,
                    pf_capped_at_ceiling=tpl.pf_capped_at_ceiling,
                    enable_esi=tpl.enable_esi,
                    enable_pt=tpl.enable_pt,
                    effective_from_date=eff_from,
                    effective_to_date=None,
                    is_current=True,
                    revision_reason="Profile Update / Template Assignment",
                )
                db.add(new_struct)

    db.commit()
    db.refresh(student)

    # Reload memory cache metadata for this tenant
    face_engine.reload_cache(db, tenant_id=current_tenant.id)

    return {
        "status": "success",
        "tenant_id": current_tenant.id,
        "message": f"Profile '{student.name}' updated successfully.",
        "student": student.to_dict(),
    }


@router.post("/student/{student_id}/transfer-department")
def transfer_student_department(
    student_id: int,
    payload: StudentDepartmentTransferPayload,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Transfers an employee/student to a new Department/Section with audit history tracking."""
    check_tenant_operational_access(current_tenant)
    student = db.query(Student).filter(
        Student.id == student_id,
        Student.tenant_id == current_tenant.id,
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Employee/Student not found.")

    target_dept = db.query(Department).filter(
        Department.tenant_id == current_tenant.id,
        Department.id == payload.department_id,
    ).first()
    if not target_dept:
        raise HTTPException(status_code=404, detail="Target department not found.")

    # Save previous state for audit & rollback
    now_ist = get_ist_now()
    student.previous_department_id = student.department_id
    student.previous_class_id = student.class_id
    student.previous_division_id = student.division_id
    student.previous_academic_year_id = student.academic_year_id
    student.last_transferred_at = now_ist

    student.department_id = target_dept.id
    student.department = target_dept.name

    if payload.class_id:
        target_class = db.query(ClassModel).filter(
            ClassModel.tenant_id == current_tenant.id,
            ClassModel.id == payload.class_id,
        ).first()
        if target_class:
            student.class_id = target_class.id
            student.class_semester = target_class.name
    if payload.division_id:
        student.division_id = payload.division_id

    db.commit()
    db.refresh(student)

    # Reload face cache
    face_engine.reload_cache(db, tenant_id=current_tenant.id)

    return {
        "status": "success",
        "message": f"Successfully transferred '{student.name}' to {target_dept.name}.",
        "student": student.to_dict(),
    }


@router.post("/student/{student_id}/relieve")
@router.post("/students/{student_id}/relieve")
def relieve_student(
    student_id: int,
    payload: StudentRelievePayload,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Relieves an active employee while preserving all historical attendance, punches, and payroll data.
    Sets is_active = False and updates employment_status to RELIEVED.
    """
    check_tenant_operational_access(current_tenant)
    student = db.query(Student).filter(
        Student.id == student_id,
        Student.tenant_id == current_tenant.id,
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Employee not found in this organization.")

    exit_reason = (payload.relieving_reason or payload.reason or "").strip()
    if not exit_reason:
        exit_reason = "Relieved from active service"

    rel_status = (payload.employment_status or "RELIEVED").strip().upper()
    now_ist = get_ist_now()

    # Parse custom relieved_at timestamp if provided
    rel_time = now_ist
    if payload.relieved_at:
        try:
            clean_ts = payload.relieved_at.replace("T", " ")
            if len(clean_ts) == 10:  # YYYY-MM-DD
                clean_ts += " 18:00:00"
            elif len(clean_ts) == 16:
                clean_ts += ":00"
            rel_time = datetime.strptime(clean_ts, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            rel_time = now_ist

    student.is_active = False
    student.employment_status = rel_status
    student.relieved_at = rel_time
    student.relieving_reason = exit_reason
    student.relieved_by_user_id = current_user.id if current_user else None

    # Log Audit Trail Entry
    audit = AuditLog(
        tenant_id=current_tenant.id,
        user_id=current_user.id if current_user else None,
        actor_name=current_user.full_name if current_user else "Admin",
        actor_role=current_user.role if current_user else "TENANT_ADMIN",
        action_type="EMPLOYEE_RELIEVED",
        target_type="EMPLOYEE",
        target_id=str(student.id),
        description=f"Relieved employee '{student.name}' ({student.roll_number}). Reason: {student.relieving_reason}",
    )
    db.add(audit)
    db.commit()
    db.refresh(student)

    # Hot-reload in-memory vector cache so relieved employee's face is deactivated from active camera nodes
    face_engine.reload_cache(db, tenant_id=current_tenant.id)

    return {
        "status": "success",
        "tenant_id": current_tenant.id,
        "message": f"Employee '{student.name}' ({student.roll_number}) has been relieved. Historical logs & payroll remain strictly preserved.",
        "student": student.to_dict(),
        "employee": student.to_dict(),
    }


@router.post("/student/{student_id}/reinstate")
@router.post("/students/{student_id}/reinstate")
def reinstate_student(
    student_id: int,
    payload: StudentReinstatePayload,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Reinstates a previously relieved employee back to active service.
    """
    check_tenant_operational_access(current_tenant)
    student = db.query(Student).filter(
        Student.id == student_id,
        Student.tenant_id == current_tenant.id,
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Employee not found in this organization.")

    student.is_active = True
    student.employment_status = "ACTIVE"
    student.relieved_at = None
    student.relieving_reason = None
    student.relieved_by_user_id = None

    # Log Audit Trail Entry
    audit = AuditLog(
        tenant_id=current_tenant.id,
        user_id=current_user.id if current_user else None,
        actor_name=current_user.full_name if current_user else "Admin",
        actor_role=current_user.role if current_user else "TENANT_ADMIN",
        action_type="EMPLOYEE_REINSTATED",
        target_type="EMPLOYEE",
        target_id=str(student.id),
        description=f"Reinstated employee '{student.name}' ({student.roll_number}) back to active service. Remarks: {payload.reason}",
    )
    db.add(audit)
    db.commit()
    db.refresh(student)

    # Hot-reload vector cache so employee can punch in again
    face_engine.reload_cache(db, tenant_id=current_tenant.id)

    return {
        "status": "success",
        "tenant_id": current_tenant.id,
        "message": f"Employee '{student.name}' ({student.roll_number}) has been reinstated to active roster.",
        "student": student.to_dict(),
        "employee": student.to_dict(),
    }


@router.post("/student/{student_id}/update-photos")
async def update_student_photos(
    student_id: int,
    photo_front: Optional[UploadFile] = File(None),
    photo_left: Optional[UploadFile] = File(None),
    photo_right: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Selectively replaces biometric face sample photos and encodings for a student."""
    check_tenant_operational_access(current_tenant)
    student = db.query(Student).filter(
        Student.id == student_id,
        Student.tenant_id == current_tenant.id,
    ).first()

    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found in this institution.")

    uploaded_files = [
        ("frontal", photo_front),
        ("left", photo_left),
        ("right", photo_right),
    ]

    valid_uploads = [(angle, f) for angle, f in uploaded_files if f and f.filename]
    if not valid_uploads:
        raise HTTPException(status_code=400, detail="Please upload at least one photo angle to update.")

    updated_angles = []
    for angle, photo_file in valid_uploads:
        contents = await photo_file.read()
        image_bgr = decode_image_bytes(contents)
        if image_bgr is None:
            raise HTTPException(status_code=400, detail=f"Invalid image file uploaded for {angle} angle.")

        is_good_quality, quality_msg = evaluate_image_quality(image_bgr)
        if not is_good_quality:
            raise HTTPException(status_code=400, detail=f"Quality check failed for {angle} photo: {quality_msg}")

        vector, face_box, msg = FaceEngine.compute_single_face_vector(image_bgr)
        if vector is None:
            raise HTTPException(status_code=400, detail=f"Face detection failed for {angle} angle photo: {msg}")

        top, right, bottom, left = face_box
        h, w = image_bgr.shape[:2]
        pad_h = int((bottom - top) * 0.15)
        pad_w = int((right - left) * 0.15)
        crop = image_bgr[
            max(0, top - pad_h): min(h, bottom + pad_h),
            max(0, left - pad_w): min(w, right + pad_w),
        ]

        timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        safe_roll = student.roll_number.replace("/", "_").replace("\\", "_")
        filename = f"t{current_tenant.id}_student_{safe_roll}_{angle}_{timestamp_str}.jpg"
        target_path = FACES_DIR / filename
        cv2.imwrite(str(target_path), crop, [cv2.IMWRITE_JPEG_QUALITY, 92])

        rel_path = f"faces/{filename}"

        # Update or add encoding
        existing_enc = (
            db.query(FaceEncoding)
            .filter(
                FaceEncoding.tenant_id == current_tenant.id,
                FaceEncoding.student_id == student.id,
                FaceEncoding.sample_angle == angle,
            )
            .first()
        )

        if existing_enc:
            existing_enc.vector_json = FaceEncoding.from_numpy(
                student_id=student.id,
                vector=vector,
                sample_angle=angle,
                photo_path=rel_path,
                tenant_id=current_tenant.id,
            ).vector_json
            existing_enc.photo_path = rel_path
        else:
            new_enc = FaceEncoding.from_numpy(
                student_id=student.id,
                vector=vector,
                sample_angle=angle,
                photo_path=rel_path,
                tenant_id=current_tenant.id,
            )
            db.add(new_enc)

        updated_angles.append(angle)

    db.commit()
    face_engine.reload_cache(db, tenant_id=current_tenant.id)

    return {
        "status": "success",
        "tenant_id": current_tenant.id,
        "message": f"Updated photo angles: {', '.join(updated_angles)} for {student.name}.",
        "student": student.to_dict(),
    }


@router.get("/student/{student_id}")
def get_student_details(
    student_id: int,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Fetches single student profile with associated photos and sample counts."""
    student = db.query(Student).filter(
        Student.id == student_id,
        Student.tenant_id == current_tenant.id,
    ).first()

    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found in this institution.")

    return {
        "status": "success",
        "tenant_id": current_tenant.id,
        "student": student.to_dict(),
    }


@router.delete("/student/{student_id}")
def delete_student_profile(
    student_id: int,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Deletes a student profile and cascading encodings/records within the tenant."""
    check_tenant_operational_access(current_tenant)
    student = db.query(Student).filter(
        Student.id == student_id,
        Student.tenant_id == current_tenant.id,
    ).first()

    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found in this institution.")

    name = student.name
    db.delete(student)
    db.commit()

    face_engine.reload_cache(db, tenant_id=current_tenant.id)

    return {
        "status": "success",
        "tenant_id": current_tenant.id,
        "message": f"Student '{name}' deleted successfully.",
    }


# ==============================================================================
# --- Tokenized Public Self-Onboarding Endpoints (Corporate & Direct Links) ---
# ==============================================================================

class OnboardRegisterRequest(BaseModel):
    tenant_uuid: str
    onboarding_token: str
    name: str
    roll_number: str  # Employee ID / Roll Number
    email: Optional[str] = None
    department_id: Optional[int] = None
    department: Optional[str] = None
    role: Optional[str] = "employee"


def resolve_onboarding_tenant(db: Session, tenant_uuid: str, onboarding_token: str) -> Tenant:
    """Helper to validate tenant UUID and onboarding token for public onboarding."""
    tenant = db.query(Tenant).filter(
        (Tenant.uuid == tenant_uuid) | (Tenant.slug == tenant_uuid),
        Tenant.onboarding_token == onboarding_token,
        Tenant.is_deleted == False,
    ).first()
    if not tenant:
        raise HTTPException(
            status_code=403,
            detail="Invalid or expired employee onboarding link. Please request a valid onboarding URL from your administrator.",
        )
    check_tenant_operational_access(tenant)
    return tenant


@router.post("/onboard/register")
def onboard_register_employee(
    payload: OnboardRegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Public self-registration endpoint for new employees using tokenized onboarding link.
    Validates tenant UUID and onboarding token.
    """
    tenant = resolve_onboarding_tenant(db, payload.tenant_uuid.strip(), payload.onboarding_token.strip())
    clean_roll = payload.roll_number.strip().upper()

    existing = db.query(Student).filter(
        Student.tenant_id == tenant.id,
        Student.roll_number == clean_roll,
    ).first()

    is_corporate = (getattr(tenant, "tenant_type", "educational") == "corporate")

    # Resolve Department
    default_dept = "General" if is_corporate else "Computer Science"
    dept_id = payload.department_id
    dept_name = (payload.department or default_dept).strip()
    if dept_id:
        dept_obj = db.query(Department).filter(Department.tenant_id == tenant.id, Department.id == dept_id).first()
        if dept_obj:
            dept_name = dept_obj.name
    else:
        dept_obj = db.query(Department).filter(Department.tenant_id == tenant.id, Department.name == dept_name).first()
        if dept_obj:
            dept_id = dept_obj.id
        else:
            # Auto-create department if not existing
            new_dept = Department(
                tenant_id=tenant.id,
                name=dept_name,
                code=dept_name[:6].upper(),
                description=f"{dept_name} Team",
            )
            db.add(new_dept)
            db.flush()
            dept_id = new_dept.id

    chosen_role = (payload.role or ("employee" if is_corporate else "student")).strip().lower()

    if existing:
        # Update existing profile if registering sample again
        existing.name = payload.name.strip()
        existing.department_id = dept_id
        existing.department = dept_name
        existing.email = payload.email.strip() if payload.email else existing.email
        existing.user_role = chosen_role
        db.commit()
        db.refresh(existing)
        student = existing
    else:
        student = Student(
            tenant_id=tenant.id,
            roll_number=clean_roll,
            name=payload.name.strip(),
            department_id=dept_id,
            department=dept_name,
            class_id=None,
            class_semester="Corporate" if is_corporate else "General",
            division_id=None,
            academic_year_id=None,
            email=payload.email.strip() if payload.email else None,
            user_role=chosen_role,
        )
        db.add(student)
        db.commit()
        db.refresh(student)

    t_uuid = tenant.uuid or tenant.slug
    checkin_url = f"/check-in/{t_uuid}/{tenant.attendance_slug}" if tenant.attendance_slug else f"/self-attendance/{tenant.slug}"

    return {
        "status": "success",
        "tenant_id": tenant.id,
        "tenant_name": tenant.name,
        "message": f"Profile '{student.name}' registered successfully. Proceed to face capture.",
        "student": student.to_dict(),
        "checkin_url": checkin_url,
    }


@router.post("/onboard/capture-sample")
async def onboard_capture_face_sample(
    tenant_uuid: str = Form(...),
    onboarding_token: str = Form(...),
    student_id: int = Form(...),
    sample_angle: str = Form("frontal"),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Public face capture endpoint for new employee onboarding using tokenized onboarding link.
    Validates face quality, extracts 128-d facial vectors, stores crop to disk, and updates engine cache.
    """
    tenant = resolve_onboarding_tenant(db, tenant_uuid.strip(), onboarding_token.strip())

    student = db.query(Student).filter(
        Student.id == student_id,
        Student.tenant_id == tenant.id,
    ).first()

    if not student:
        raise HTTPException(status_code=404, detail="Employee profile not found.")

    # Read image
    contents = await image.read()
    image_bgr = decode_image_bytes(contents)
    if image_bgr is None:
        raise HTTPException(status_code=400, detail="Invalid camera capture image.")

    # Evaluate image quality
    is_good_quality, quality_msg = evaluate_image_quality(image_bgr)
    if not is_good_quality:
        raise HTTPException(status_code=400, detail=f"Image quality check failed: {quality_msg}")

    # Extract 128-d vector and face bounding box
    vector, face_box, msg = FaceEngine.compute_single_face_vector(image_bgr)
    if vector is None:
        raise HTTPException(status_code=400, detail=msg or "No clear face detected. Look directly into the camera.")

    # Crop reference face image
    top, right, bottom, left = face_box
    h, w = image_bgr.shape[:2]
    pad_h = int((bottom - top) * 0.15)
    pad_w = int((right - left) * 0.15)
    crop = image_bgr[
        max(0, top - pad_h): min(h, bottom + pad_h),
        max(0, left - pad_w): min(w, right + pad_w),
    ]

    timestamp_str = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    clean_roll = student.roll_number.replace("/", "_").replace("\\", "_")
    filename = f"t{tenant.id}_student_{clean_roll}_{sample_angle}_{timestamp_str}.jpg"
    target_path = FACES_DIR / filename
    cv2.imwrite(str(target_path), crop, [cv2.IMWRITE_JPEG_QUALITY, 92])

    rel_path = f"faces/{filename}"

    # Upsert face encoding record
    existing_sample = (
        db.query(FaceEncoding)
        .filter(
            FaceEncoding.tenant_id == tenant.id,
            FaceEncoding.student_id == student.id,
            FaceEncoding.sample_angle == sample_angle,
        )
        .first()
    )
    if existing_sample:
        existing_sample.vector_json = FaceEncoding.from_numpy(
            student_id=student.id,
            vector=vector,
            sample_angle=sample_angle,
            photo_path=rel_path,
            tenant_id=tenant.id,
        ).vector_json
        existing_sample.photo_path = rel_path
    else:
        encoding_record = FaceEncoding.from_numpy(
            student_id=student.id,
            vector=vector,
            sample_angle=sample_angle,
            photo_path=rel_path,
            tenant_id=tenant.id,
        )
        db.add(encoding_record)

    db.commit()

    # Hot-reload in-memory vector cache for this tenant
    face_engine.reload_cache(db, tenant_id=tenant.id)

    total_samples = db.query(FaceEncoding).filter(
        FaceEncoding.tenant_id == tenant.id,
        FaceEncoding.student_id == student.id,
    ).count()

    t_uuid = tenant.uuid or tenant.slug
    checkin_url = f"/check-in/{t_uuid}/{tenant.attendance_slug}" if tenant.attendance_slug else f"/self-attendance/{tenant.slug}"

    return {
        "status": "success",
        "tenant_id": tenant.id,
        "student_id": student.id,
        "sample_angle": sample_angle,
        "total_samples": total_samples,
        "message": f"Biometric face sample ({sample_angle}) registered and indexed successfully.",
        "checkin_url": checkin_url,
    }
