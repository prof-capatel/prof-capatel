import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status, File, Form, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.core.camera_utils import decode_image_bytes
from src.core.face_engine import face_engine
from src.database.models import User, Tenant, AuditLog, Student
from src.database.session import get_db
from src.server.tenant_middleware import get_current_tenant, resolve_tenant
from src.server.rbac_middleware import (
    create_access_token,
    get_current_user,
    get_current_user_optional,
    check_tenant_login_access,
)
from src.utils.auth_utils import verify_password, hash_password
from src.utils.timezone import get_ist_now

logger = logging.getLogger("api_auth")
router = APIRouter(prefix="/api/v1/auth", tags=["Authentication & RBAC"])


class LoginRequest(BaseModel):
    username: str
    password: str
    tenant_id: Optional[int] = None


class SwitchRoleRequest(BaseModel):
    role: str  # SUPER_ADMIN, TENANT_ADMIN, TEACHER, STUDENT
    tenant_id: Optional[int] = 1


@router.post("/login")
def login(
    payload: LoginRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Authenticates a user with username & password.
    Supports global SUPER_ADMIN as well as tenant-scoped TENANT_ADMIN, TEACHER, STUDENT.
    """
    username_clean = payload.username.strip().lower()
    
    # Check if Super Admin
    user = db.query(User).filter(User.username == username_clean, User.role == "SUPER_ADMIN", User.is_active == True).first()
    
    if not user:
        # Search by tenant-scoped username
        tenant_id = payload.tenant_id or 1
        user = db.query(User).filter(
            User.username == username_clean,
            User.tenant_id == tenant_id,
            User.is_active == True,
        ).first()

    if not user:
        # Fallback search across any active user if tenant_id wasn't specified
        user = db.query(User).filter(
            User.username == username_clean,
            User.is_active == True,
        ).first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    # If tenant-scoped user, check that tenant is not soft-deleted
    if user.tenant_id and user.tenant:
        check_tenant_login_access(user.tenant)

    user.last_login_at = get_ist_now()
    db.commit()

    token = create_access_token(
        user_id=user.id,
        role=user.role,
        tenant_id=user.tenant_id,
        username=user.username,
    )

    # Set secure cookies for browser navigation
    response.set_cookie("access_token", token, httponly=True, max_age=86400, path="/")
    response.set_cookie("active_role", user.role, httponly=False, max_age=86400, path="/")
    if user.tenant_id:
        response.set_cookie("active_tenant_id", str(user.tenant_id), httponly=False, max_age=86400, path="/")
    else:
        response.delete_cookie("active_tenant_id", path="/")

    # Record Audit Log
    try:
        audit = AuditLog(
            tenant_id=user.tenant_id,
            user_id=user.id,
            actor_name=user.full_name,
            actor_role=user.role,
            action_type="USER_LOGIN",
            target_type="USER",
            target_id=str(user.id),
            description=f"User '{user.username}' logged in successfully.",
            ip_address=request.client.host if request.client else None,
        )
        db.add(audit)
        db.commit()
    except Exception as e:
        logger.warning(f"Audit log recording error: {e}")

    return {
        "status": "success",
        "message": f"Welcome back, {user.full_name}!",
        "access_token": token,
        "token_type": "bearer",
        "user": user.to_dict(),
    }


@router.post("/face-login")
async def face_login(
    frame: UploadFile = File(...),
    tenant_slug: Optional[str] = Form(None),
    response: Response = None,
    request: Request = None,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """
    Biometric Face-Based Login for Flutter Web & Mobile Clients.
    Takes a camera snapshot, matches face against 1:N tenant vectors,
    and returns authenticated user/student profile with JWT bearer token.
    """
    target_tenant = current_tenant
    if tenant_slug:
        t = resolve_tenant(db, tenant_slug)
        if t:
            target_tenant = t

    check_tenant_login_access(target_tenant)

    # 1. Read & decode image
    contents = await frame.read()
    image_bgr = decode_image_bytes(contents)
    if image_bgr is None:
        raise HTTPException(status_code=400, detail="Invalid camera frame.")

    # 2. Biometric matching
    try:
        detections = face_engine.detect_and_recognize_faces(
            image_bgr,
            node_id="FLUTTER-FACE-LOGIN",
            tenant_id=target_tenant.id,
            is_single_shot=True,
            enable_anti_spoofing=True,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Face recognition error: {str(e)}")

    if len(detections) == 0:
        raise HTTPException(status_code=400, detail="No face detected. Center your face with clear lighting.")

    if len(detections) > 1:
        raise HTTPException(status_code=400, detail=f"Multiple faces ({len(detections)}) detected. Only 1 person allowed.")

    det = detections[0]
    if not det.get("is_live", True):
        raise HTTPException(status_code=400, detail="Liveness check failed. Look directly into the camera.")

    if not det.get("is_match", False) or det.get("student_id") is None:
        raise HTTPException(status_code=404, detail="Face not recognized in institution records.")

    student = db.query(Student).filter(Student.id == det["student_id"], Student.tenant_id == target_tenant.id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found.")

    # Find or link User account if exists, else create student payload token
    user = None
    if student.user_id:
        user = db.query(User).filter(User.id == student.user_id).first()

    user_id = user.id if user else student.id
    role = user.role if user else (student.user_role.upper() if student.user_role else "STUDENT")
    username = user.username if user else student.roll_number
    full_name = user.full_name if user else student.name

    token = create_access_token(
        user_id=user_id,
        role=role,
        tenant_id=target_tenant.id,
        username=username,
    )

    if response:
        response.set_cookie("access_token", token, httponly=True, max_age=86400, path="/")
        response.set_cookie("active_role", role, httponly=False, max_age=86400, path="/")
        response.set_cookie("active_tenant_id", str(target_tenant.id), httponly=False, max_age=86400, path="/")

    return {
        "status": "success",
        "message": f"Authenticated as {full_name}!",
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user_id,
            "student_id": student.id,
            "username": username,
            "name": full_name,
            "role": role,
            "tenant_id": target_tenant.id,
            "tenant_name": target_tenant.name,
            "roll_number": student.roll_number,
            "department": student.department,
            "class_semester": student.class_obj.name if student.class_obj else student.class_semester,
            "division_name": student.division_obj.name if student.division_obj else "N/A",
        },
        "confidence_pct": det.get("confidence_pct", 0.0),
    }


@router.post("/logout")
def logout(response: Response):
    """Logs out user by clearing session cookies."""
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("active_role", path="/")
    return {"status": "success", "message": "Logged out successfully."}


@router.get("/me")
def get_current_user_profile(
    user: User = Depends(get_current_user),
):
    """Retrieves profile and permissions of current authenticated user."""
    return {
        "status": "success",
        "user": user.to_dict(),
    }


@router.post("/switch-role")
def switch_dev_role(
    payload: SwitchRoleRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Developer/Demo endpoint for instantly switching active session role
    between SUPER_ADMIN, TENANT_ADMIN, TEACHER, and STUDENT.
    """
    target_role = payload.role.strip().upper()
    tenant_id = payload.tenant_id or 1

    if target_role == "SUPER_ADMIN":
        user = db.query(User).filter(User.role == "SUPER_ADMIN", User.is_active == True).first()
    else:
        user = db.query(User).filter(
            User.tenant_id == tenant_id,
            User.role == target_role,
            User.is_active == True,
        ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail=f"No active user found with role '{target_role}' in Tenant #{tenant_id}.",
        )

    token = create_access_token(
        user_id=user.id,
        role=user.role,
        tenant_id=user.tenant_id,
        username=user.username,
    )

    response.set_cookie("access_token", token, httponly=True, max_age=86400, path="/")
    response.set_cookie("active_role", user.role, httponly=False, max_age=86400, path="/")
    if user.tenant_id:
        response.set_cookie("active_tenant_id", str(user.tenant_id), httponly=False, max_age=86400, path="/")

    return {
        "status": "success",
        "message": f"Switched role to {user.role} ({user.full_name}).",
        "user": user.to_dict(),
        "access_token": token,
    }
