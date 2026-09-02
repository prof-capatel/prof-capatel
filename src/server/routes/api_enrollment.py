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
from src.database.models import Student, FaceEncoding
from src.database.session import get_db

router = APIRouter(prefix="/api/v1/enroll", tags=["Student Enrollment"])


class StudentCreate(BaseModel):
    roll_number: str
    name: str
    department: Optional[str] = "Computer Science"
    email: Optional[str] = None


class StudentUpdate(BaseModel):
    roll_number: str
    name: str
    department: Optional[str] = "Computer Science"
    email: Optional[str] = None


@router.post("/student")
def register_student(payload: StudentCreate, db: Session = Depends(get_db)):
    """Registers a new student profile before capturing face samples."""
    existing = db.query(Student).filter(Student.roll_number == payload.roll_number.strip()).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Student with Roll Number '{payload.roll_number}' already exists.",
        )

    student = Student(
        roll_number=payload.roll_number.strip().upper(),
        name=payload.name.strip(),
        department=payload.department.strip() if payload.department else "Computer Science",
        email=payload.email.strip() if payload.email else None,
    )
    db.add(student)
    db.commit()
    db.refresh(student)

    return {
        "status": "success",
        "message": f"Student '{student.name}' registered successfully.",
        "student": student.to_dict(),
    }


@router.post("/capture-sample")
async def capture_face_sample(
    student_id: int = Form(...),
    sample_angle: str = Form("frontal"),  # frontal, left, right
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Validates, extracts 128-d facial vector from uploaded frame,
    persists sample to DB and disk, and refreshes the in-memory FaceEngine cache.
    """
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

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
    # Pad crop slightly
    h, w = image_bgr.shape[:2]
    pad_h = int((bottom - top) * 0.15)
    pad_w = int((right - left) * 0.15)
    c_top = max(0, top - pad_h)
    c_bottom = min(h, bottom + pad_h)
    c_left = max(0, left - pad_w)
    c_right = min(w, right + pad_w)
    
    face_crop = image_bgr[c_top:c_bottom, c_left:c_right]
    
    filename = f"student_{student.roll_number}_{sample_angle}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.jpg"
    file_path = FACES_DIR / filename
    cv2.imwrite(str(file_path), face_crop)

    # Save encoding in database
    encoding_record = FaceEncoding.from_numpy(
        student_id=student.id,
        vector=vector,
        sample_angle=sample_angle,
        photo_path=f"faces/{filename}",
    )
    db.add(encoding_record)
    db.commit()

    # Hot reload the in-memory cache
    face_engine.reload_cache(db)

    # Count total samples for student
    sample_count = db.query(FaceEncoding).filter(FaceEncoding.student_id == student.id).count()

    return {
        "status": "success",
        "message": f"Sample '{sample_angle}' enrolled successfully!",
        "sample_count": sample_count,
        "photo_url": f"/data/faces/{filename}",
    }


@router.post("/batch-upload")
async def enroll_student_batch(
    roll_number: str = Form(...),
    name: str = Form(...),
    department: Optional[str] = Form("Computer Science"),
    email: Optional[str] = Form(None),
    images: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """
    Dual-Mode Registration: Batch uploads exactly 3 clear photos for a student.
    Processes all 3 images, extracts 128-d face vectors for each,
    saves cropped reference images, persists embeddings to SQLite,
    and hot-reloads the in-memory recognition cache.
    """
    clean_roll = roll_number.strip().upper()
    clean_name = name.strip()
    
    if not clean_roll or not clean_name:
        raise HTTPException(status_code=400, detail="Student Name and Roll Number are required.")

    if len(images) != 3:
        raise HTTPException(
            status_code=400,
            detail=f"Exactly 3 photos are required for multi-angle enrollment. Received: {len(images)}.",
        )

    # 1. Check or create student
    student = db.query(Student).filter(Student.roll_number == clean_roll).first()
    if not student:
        student = Student(
            roll_number=clean_roll,
            name=clean_name,
            department=department.strip() if department else "Computer Science",
            email=email.strip() if email else None,
        )
        db.add(student)
        db.flush()
    else:
        student.name = clean_name
        if department:
            student.department = department.strip()
        if email:
            student.email = email.strip()

    # 2. Process all 3 images
    sample_tags = ["frontal", "left_angle", "right_angle"]
    saved_encodings = []
    photo_urls = []

    for idx, (img_file, tag) in enumerate(zip(images, sample_tags), start=1):
        contents = await img_file.read()
        image_bgr = decode_image_bytes(contents)
        if image_bgr is None:
            raise HTTPException(status_code=400, detail=f"Photo #{idx} ({img_file.filename}) is an invalid or corrupted image.")

        # Check face & extract 128-d vector
        vector, face_box, msg = FaceEngine.compute_single_face_vector(image_bgr)
        if vector is None or face_box is None:
            raise HTTPException(
                status_code=400,
                detail=f"Photo #{idx} ({img_file.filename}) face detection failed: {msg}",
            )

        # Crop and save reference face image
        top, right, bottom, left = face_box
        h, w = image_bgr.shape[:2]
        pad_h = int((bottom - top) * 0.15)
        pad_w = int((right - left) * 0.15)
        c_top = max(0, top - pad_h)
        c_bottom = min(h, bottom + pad_h)
        c_left = max(0, left - pad_w)
        c_right = min(w, right + pad_w)

        face_crop = image_bgr[c_top:c_bottom, c_left:c_right]
        filename = f"std_{clean_roll}_{tag}_{datetime.utcnow().strftime('%Y%m%d%H%M%S_%f')}.jpg"
        file_path = FACES_DIR / filename
        cv2.imwrite(str(file_path), face_crop)

        encoding_record = FaceEncoding.from_numpy(
            student_id=student.id,
            vector=vector,
            sample_angle=tag,
            photo_path=f"faces/{filename}",
        )
        saved_encodings.append(encoding_record)
        photo_urls.append(f"/data/faces/{filename}")

    # 3. Persist all encodings to database
    for enc in saved_encodings:
        db.add(enc)
    db.commit()

    # 4. Hot reload in-memory FaceEngine vector cache
    face_engine.reload_cache(db)

    total_samples = db.query(FaceEncoding).filter(FaceEncoding.student_id == student.id).count()

    return {
        "status": "success",
        "message": f"Successfully enrolled student '{student.name}' with 3 multi-angle face vectors.",
        "student": student.to_dict(),
        "total_samples": total_samples,
        "photo_urls": photo_urls,
    }


@router.get("/students")
def list_students(db: Session = Depends(get_db)):
    """Lists all registered students with sample counts."""
    students = db.query(Student).order_by(Student.name.asc()).all()
    return {"students": [s.to_dict() for s in students]}


@router.get("/student/{student_id}")
def get_student(student_id: int, db: Session = Depends(get_db)):
    """Retrieves full student details and enrolled reference photos."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")
    return {"status": "success", "student": student.to_dict()}


@router.put("/student/{student_id}")
def update_student(student_id: int, payload: StudentUpdate, db: Session = Depends(get_db)):
    """Updates student profile information (Name, Roll Number, Department, Email)."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    clean_roll = payload.roll_number.strip().upper()
    clean_name = payload.name.strip()

    if not clean_roll or not clean_name:
        raise HTTPException(status_code=400, detail="Name and Roll Number cannot be empty.")

    # Check roll number uniqueness if changed
    if clean_roll != student.roll_number:
        conflict = db.query(Student).filter(Student.roll_number == clean_roll, Student.id != student_id).first()
        if conflict:
            raise HTTPException(status_code=400, detail=f"Roll Number '{clean_roll}' is already in use by another student.")

    student.roll_number = clean_roll
    student.name = clean_name
    student.department = payload.department.strip() if payload.department else "Computer Science"
    student.email = payload.email.strip() if payload.email else None

    db.commit()
    db.refresh(student)

    # Hot reload FaceEngine cache so recognition labels immediately reflect updated name/roll
    face_engine.reload_cache(db)

    return {
        "status": "success",
        "message": f"Student profile for '{student.name}' updated successfully.",
        "student": student.to_dict(),
    }


@router.post("/student/{student_id}/update-photos")
async def update_student_photos(
    student_id: int,
    images: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """
    Overwrites the student's reference face photos and embeddings with 3 new photos.
    Extracts 128-d vectors from all 3 images, replaces old encodings in SQLite,
    and hot-reloads the in-memory FaceEngine cache.
    """
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    if len(images) != 3:
        raise HTTPException(
            status_code=400,
            detail=f"Exactly 3 photos are required for multi-angle face enrollment. Received: {len(images)}.",
        )

    # 1. Process and validate all 3 images
    sample_tags = ["frontal", "left_angle", "right_angle"]
    saved_encodings = []
    photo_urls = []

    for idx, (img_file, tag) in enumerate(zip(images, sample_tags), start=1):
        contents = await img_file.read()
        image_bgr = decode_image_bytes(contents)
        if image_bgr is None:
            raise HTTPException(status_code=400, detail=f"Photo #{idx} ({img_file.filename}) is invalid or corrupted.")

        # Face detection and 128-d vector extraction
        vector, face_box, msg = FaceEngine.compute_single_face_vector(image_bgr)
        if vector is None or face_box is None:
            raise HTTPException(
                status_code=400,
                detail=f"Photo #{idx} ({img_file.filename}) face detection failed: {msg}",
            )

        # Crop and save reference face crop
        top, right, bottom, left = face_box
        h, w = image_bgr.shape[:2]
        pad_h = int((bottom - top) * 0.15)
        pad_w = int((right - left) * 0.15)
        c_top = max(0, top - pad_h)
        c_bottom = min(h, bottom + pad_h)
        c_left = max(0, left - pad_w)
        c_right = min(w, right + pad_w)

        face_crop = image_bgr[c_top:c_bottom, c_left:c_right]
        filename = f"std_{student.roll_number}_{tag}_{datetime.utcnow().strftime('%Y%m%d%H%M%S_%f')}.jpg"
        file_path = FACES_DIR / filename
        cv2.imwrite(str(file_path), face_crop)

        encoding_record = FaceEncoding.from_numpy(
            student_id=student.id,
            vector=vector,
            sample_angle=tag,
            photo_path=f"faces/{filename}",
        )
        saved_encodings.append(encoding_record)
        photo_urls.append(f"/data/faces/{filename}")

    # 2. Remove previous encodings for this student
    db.query(FaceEncoding).filter(FaceEncoding.student_id == student.id).delete()

    # 3. Add new encodings
    for enc in saved_encodings:
        db.add(enc)
    db.commit()

    # 4. Hot reload FaceEngine cache
    face_engine.reload_cache(db)

    return {
        "status": "success",
        "message": f"Successfully updated 3 reference photos and re-trained embeddings for '{student.name}'.",
        "student": student.to_dict(),
        "photo_urls": photo_urls,
    }


@router.delete("/student/{student_id}")
def delete_student(student_id: int, db: Session = Depends(get_db)):
    """Deletes a student and all their face encodings and attendance records."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    db.delete(student)
    db.commit()

    # Hot reload cache
    face_engine.reload_cache(db)

    return {"status": "success", "message": f"Student '{student.name}' deleted."}
