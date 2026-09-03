from datetime import datetime
from pathlib import Path
from typing import List, Optional
import cv2
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.config import FACES_DIR
from src.core.camera_utils import decode_image_bytes, evaluate_image_quality
from src.core.face_engine import face_engine, FaceEngine
from src.database.models import Student, FaceEncoding, Tenant
from src.database.session import get_db
from src.server.tenant_middleware import get_current_tenant

router = APIRouter(prefix="/api/v1/enroll", tags=["Student Enrollment"])


class StudentCreate(BaseModel):
    roll_number: str
    name: str
    department: Optional[str] = "Computer Science"
    email: Optional[str] = None
    user_role: Optional[str] = "student"
    class_semester: Optional[str] = "General"


class StudentUpdate(BaseModel):
    roll_number: str
    name: str
    department: Optional[str] = "Computer Science"
    email: Optional[str] = None
    user_role: Optional[str] = "student"
    class_semester: Optional[str] = "General"


@router.post("/student")
def register_student(
    payload: StudentCreate,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Registers a new student profile before capturing face samples scoped to current tenant."""
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

    student = Student(
        tenant_id=current_tenant.id,
        roll_number=clean_roll,
        name=payload.name.strip(),
        department=payload.department.strip() if payload.department else "Computer Science",
        email=payload.email.strip() if payload.email else None,
        user_role=payload.user_role.strip().lower() if payload.user_role else "student",
        class_semester=payload.class_semester.strip() if payload.class_semester else "General",
    )
    db.add(student)
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
    department: str = Form("Computer Science"),
    email: Optional[str] = Form(None),
    user_role: str = Form("student"),
    class_semester: Optional[str] = Form("General"),
    photo_front: UploadFile = File(...),
    photo_left: UploadFile = File(...),
    photo_right: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """
    All-in-one 3-photo batch enrollment: creates student profile, processes 3 photos,
    extracts vectors, and hot-reloads vector memory cache for current tenant.
    """
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

    # Save Student
    student = Student(
        tenant_id=current_tenant.id,
        roll_number=clean_roll,
        name=name.strip(),
        department=department.strip(),
        email=email.strip() if email else None,
        user_role=user_role.strip().lower() if user_role else "student",
        class_semester=class_semester.strip() if class_semester else "General",
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

    student.roll_number = clean_roll
    student.name = payload.name.strip()
    student.department = payload.department.strip() if payload.department else "Computer Science"
    student.email = payload.email.strip() if payload.email else None
    student.user_role = payload.user_role.strip().lower() if payload.user_role else "student"
    student.class_semester = payload.class_semester.strip() if payload.class_semester else "General"

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
