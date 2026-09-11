import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status, File, Form, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

import base64
import numpy as np
from src.core.camera_utils import decode_image_bytes
from src.core.face_engine import face_engine, FaceEngine
from src.database.models import User, Tenant, AuditLog, Student, FaceEncoding
from src.database.session import get_db
from src.server.tenant_middleware import get_current_tenant, resolve_tenant
from src.server.rbac_middleware import (
    create_access_token,
    get_current_user,
    get_current_user_optional,
    check_tenant_login_access,
)
from src.server.routes.api_employee_portal import create_employee_token
from src.utils.auth_utils import verify_password, hash_password
from src.utils.timezone import get_ist_now
from sqlalchemy import or_, and_

logger = logging.getLogger("api_auth")
router = APIRouter(prefix="/api/v1/auth", tags=["Authentication & RBAC"])


class LoginRequest(BaseModel):
    username: str
    password: str
    tenant_id: Optional[int] = None
    role: Optional[str] = None


class SuperAdminLoginRequest(BaseModel):
    username: str
    password: str


class TenantLoginRequest(BaseModel):
    username: str
    password: str
    tenant_identifier: Optional[str] = None
    tenant_id: Optional[int] = None
    role: Optional[str] = None


class TenantFaceLoginRequest(BaseModel):
    tenant_identifier: str
    photo_base64: str


class SwitchRoleRequest(BaseModel):
    role: str  # SUPER_ADMIN, TENANT_ADMIN, TEACHER, STUDENT, EMPLOYEE
    tenant_id: Optional[int] = 1


@router.post("/super-admin/login")
def super_admin_login(
    payload: SuperAdminLoginRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Dedicated, isolated login endpoint exclusively for Super Administrators.
    Completely decoupled from multi-tenant contexts and tenant dropdowns.
    """
    username_clean = payload.username.strip().lower()
    user = db.query(User).filter(
        User.username == username_clean,
        User.role == "SUPER_ADMIN",
        User.is_active == True,
    ).first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Super Administrator credentials.",
        )

    user.last_login_at = get_ist_now()
    db.commit()

    token = create_access_token(
        user_id=user.id,
        role="SUPER_ADMIN",
        tenant_id=None,
        username=user.username,
    )

    # Set secure Super Admin session cookies (clear any active_tenant_id)
    response.set_cookie("access_token", token, httponly=True, max_age=86400, path="/")
    response.set_cookie("active_role", "SUPER_ADMIN", httponly=False, max_age=86400, path="/")
    response.delete_cookie("active_tenant_id", path="/")

    # Record Audit Log
    try:
        audit = AuditLog(
            tenant_id=None,
            user_id=user.id,
            actor_name=user.full_name,
            actor_role="SUPER_ADMIN",
            action_type="SUPER_ADMIN_LOGIN",
            target_type="SYSTEM",
            target_id="CONTROL_PLANE",
            description=f"Super Admin '{user.username}' authenticated via dedicated login portal.",
            ip_address=request.client.host if request.client else None,
        )
        db.add(audit)
        db.commit()
    except Exception as e:
        logger.warning(f"Audit log recording error: {e}")

    return {
        "status": "success",
        "message": f"Welcome to Global Control Plane, {user.full_name}!",
        "access_token": token,
        "token_type": "bearer",
        "user": user.to_dict(),
        "redirect_url": "/super-admin",
    }


@router.post("/tenant/login")
def tenant_portal_login(
    payload: TenantLoginRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Dedicated, isolated login endpoint for tenant-specific unique portals.
    Authenticates users strictly within the bounds of that specific organization.
    """
    username_clean = payload.username.strip().lower()
    
    # 1. Resolve tenant
    target_tenant = None
    if payload.tenant_id:
        target_tenant = db.query(Tenant).filter(Tenant.id == payload.tenant_id, Tenant.is_deleted == False).first()
    elif payload.tenant_identifier:
        clean_id = str(payload.tenant_identifier).strip().lower()
        target_tenant = db.query(Tenant).filter(
            (Tenant.slug == clean_id) | (Tenant.uuid == str(payload.tenant_identifier).strip()),
            Tenant.is_deleted == False,
        ).first()

    if not target_tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target organization not found or is deactivated.",
        )

    check_tenant_login_access(target_tenant)

    # 2. Query user strictly within this tenant
    query = db.query(User).filter(
        User.username == username_clean,
        User.tenant_id == target_tenant.id,
        User.is_active == True,
    )
    if payload.role:
        role_clean = payload.role.strip().upper()
        user = query.filter(User.role == role_clean).first()
    else:
        user = None

    if not user:
        user = query.first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid credentials for {target_tenant.name}.",
        )

    user.last_login_at = get_ist_now()
    db.commit()

    token = create_access_token(
        user_id=user.id,
        role=user.role,
        tenant_id=target_tenant.id,
        username=user.username,
    )

    # Set secure tenant-scoped session cookies
    response.set_cookie("access_token", token, httponly=True, max_age=86400, path="/")
    response.set_cookie("active_role", user.role, httponly=False, max_age=86400, path="/")
    response.set_cookie("active_tenant_id", str(target_tenant.id), httponly=False, max_age=86400, path="/")

    # Determine redirect url
    if user.role == "TEACHER":
        redirect_url = "/teacher-portal"
    elif user.role in ["STUDENT", "EMPLOYEE"]:
        redirect_url = "/logs"
    else:
        redirect_url = "/"

    # Record Audit Log
    try:
        audit = AuditLog(
            tenant_id=target_tenant.id,
            user_id=user.id,
            actor_name=user.full_name,
            actor_role=user.role,
            action_type="TENANT_PORTAL_LOGIN",
            target_type="TENANT",
            target_id=str(target_tenant.id),
            description=f"User '{user.username}' ({user.role}) logged in to {target_tenant.name} portal.",
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
        "tenant": target_tenant.to_dict(),
        "redirect_url": redirect_url,
    }


@router.post("/tenant/face-login")
def tenant_face_login(
    payload: TenantFaceLoginRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Passwordless Face-Authentication Login for Tenant Portals.
    Matches 128-d face embedding against active registered users/employees in the tenant.
    Auto-detects whether the user is an Administrator or Employee and issues appropriate role session cookies.
    """
    target_tenant = resolve_tenant(db, payload.tenant_identifier)
    if not target_tenant or not target_tenant.is_active or target_tenant.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target organization not found or is currently deactivated.",
        )

    check_tenant_login_access(target_tenant)

    # 1. Decode incoming image
    raw_b64 = payload.photo_base64
    if "," in raw_b64:
        raw_b64 = raw_b64.split(",", 1)[1]

    try:
        image_bytes = base64.b64decode(raw_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Malformed base64 image data.")

    image_bgr = decode_image_bytes(image_bytes)
    if image_bgr is None:
        raise HTTPException(status_code=400, detail="Could not decode camera image frame.")

    # 2. Extract Face Vector
    vector, face_box, msg = FaceEngine.compute_single_face_vector(image_bgr)
    if vector is None:
        raise HTTPException(
            status_code=400,
            detail=f"Face detection failed: {msg}. Please center your face clearly in the camera frame.",
        )

    # 3. Retrieve active Face Encodings for this Tenant
    encodings = (
        db.query(FaceEncoding)
        .join(Student, FaceEncoding.student_id == Student.id)
        .filter(
            FaceEncoding.tenant_id == target_tenant.id,
            Student.is_active == True,
            or_(Student.employment_status == "ACTIVE", Student.employment_status == None),
        )
        .all()
    )

    if not encodings:
        raise HTTPException(
            status_code=404,
            detail="No enrolled face profiles found for this organization. Please contact your administrator or sign in with credentials.",
        )

    # 4. Compare Euclidean Distance
    branding = target_tenant.branding
    threshold = float(branding.self_attendance_face_threshold if branding and branding.self_attendance_face_threshold else 0.52)

    best_match_student = None
    min_dist = float("inf")

    for enc in encodings:
        try:
            sample_vec = enc.get_numpy_vector()
            dist = float(np.linalg.norm(sample_vec - vector))
            if dist < min_dist:
                min_dist = dist
                if dist <= threshold:
                    best_match_student = enc.student
        except Exception as e:
            logger.debug(f"Vector comparison error: {e}")

    if not best_match_student:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Face not recognized (distance: {round(min_dist, 3)}, threshold: {threshold}). Please center your face in good light or sign in with password.",
        )

    if not best_match_student.is_active or (best_match_student.employment_status and best_match_student.employment_status.upper() in ["RELIEVED", "TERMINATED", "RESIGNED"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account for '{best_match_student.name}' is relieved or inactive. Access restricted.",
        )

    # 5. Determine Role and Session
    # Check if user has a TENANT_ADMIN user account linked
    admin_user = None
    if best_match_student.user_id:
        admin_user = db.query(User).filter(User.id == best_match_student.user_id, User.tenant_id == target_tenant.id, User.is_active == True).first()
    
    if not admin_user:
        admin_user = db.query(User).filter(
            User.tenant_id == target_tenant.id,
            User.username == best_match_student.roll_number,
            User.role == "TENANT_ADMIN",
            User.is_active == True,
        ).first()

    is_admin = (admin_user and admin_user.role == "TENANT_ADMIN") or (best_match_student.user_role and best_match_student.user_role.lower() in ["admin", "tenant_admin"])

    if is_admin:
        effective_role = "TENANT_ADMIN"
        user_id_for_token = admin_user.id if admin_user else best_match_student.id
        username_for_token = admin_user.username if admin_user else best_match_student.roll_number
        redirect_url = "/"
        
        token = create_access_token(
            user_id=user_id_for_token,
            role=effective_role,
            tenant_id=target_tenant.id,
            username=username_for_token,
        )
    else:
        effective_role = "EMPLOYEE"
        redirect_url = f"/employee/{target_tenant.slug}/dashboard"
        
        token = create_access_token(
            user_id=best_match_student.id,
            role=effective_role,
            tenant_id=target_tenant.id,
            username=best_match_student.roll_number,
        )
        
        emp_token = create_employee_token(
            student_id=best_match_student.id,
            tenant_id=target_tenant.id,
            roll_number=best_match_student.roll_number,
            name=best_match_student.name,
            expires_in_sec=86400,
        )
        response.set_cookie("emp_session_token", emp_token, httponly=True, max_age=86400, path="/")

    # Set common session cookies
    response.set_cookie("access_token", token, httponly=True, max_age=86400, path="/")
    response.set_cookie("active_role", effective_role, httponly=False, max_age=86400, path="/")
    response.set_cookie("active_tenant_id", str(target_tenant.id), httponly=False, max_age=86400, path="/")

    # Update last login
    if admin_user:
        admin_user.last_login_at = get_ist_now()
        db.commit()

    # Log Audit
    try:
        audit = AuditLog(
            tenant_id=target_tenant.id,
            user_id=admin_user.id if admin_user else None,
            actor_name=best_match_student.name,
            actor_role=effective_role,
            action_type="PORTAL_FACE_LOGIN",
            target_type="TENANT",
            target_id=str(target_tenant.id),
            description=f"Face authentication login for '{best_match_student.name}' ({effective_role}) into {target_tenant.name} portal (dist: {round(min_dist, 3)}).",
            ip_address=request.client.host if request.client else None,
        )
        db.add(audit)
        db.commit()
    except Exception as e:
        logger.warning(f"Audit recording note: {e}")

    return {
        "status": "success",
        "message": f"Welcome back, {best_match_student.name}!",
        "user_name": best_match_student.name,
        "roll_number": best_match_student.roll_number,
        "role": effective_role,
        "is_admin": is_admin,
        "access_token": token,
        "redirect_url": redirect_url,
        "distance": round(min_dist, 3),
    }


@router.get("/tenant-roles/{tenant_identifier}")
def get_tenant_roles(
    tenant_identifier: str,
    db: Session = Depends(get_db),
):
    """
    Returns available user roles and institutional profile for a specific tenant login portal.
    """
    clean_id = tenant_identifier.strip().lower()
    tenant = db.query(Tenant).filter(
        (Tenant.slug == clean_id) | (Tenant.uuid == tenant_identifier.strip()),
        Tenant.is_deleted == False,
    ).first()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization '{tenant_identifier}' not found or has been deactivated.",
        )

    t_type = (tenant.tenant_type or "educational").lower()
    is_corporate = t_type in ["corporate", "company", "enterprise"]

    if is_corporate:
        roles = [
            {"key": "TENANT_ADMIN", "label": "Tenant Administrator", "icon": "fa-user-shield", "description": "Full enterprise administration & access controls"},
            {"key": "EMPLOYEE", "label": "Employee", "icon": "fa-id-badge", "description": "Personal attendance logs & self check-in"},
        ]
    else:
        roles = [
            {"key": "TENANT_ADMIN", "label": "Tenant Administrator", "icon": "fa-user-shield", "description": "Campus administration & node management"},
            {"key": "TEACHER", "label": "Teacher / Faculty", "icon": "fa-chalkboard-user", "description": "Classroom attendance & rosters"},
            {"key": "STUDENT", "label": "Student", "icon": "fa-user-graduate", "description": "Student turnout logs & history"},
        ]

    # Check for active demo users in this tenant for quick-login assistance
    demo_users = []
    tenant_admin = db.query(User).filter(User.tenant_id == tenant.id, User.role == "TENANT_ADMIN", User.is_active == True).first()
    if tenant_admin:
        demo_users.append({
            "role": "TENANT_ADMIN",
            "role_label": "Tenant Admin",
            "username": tenant_admin.username,
            "full_name": tenant_admin.full_name,
            "icon": "fa-user-shield",
        })

    if is_corporate:
        first_emp = db.query(Student).filter(Student.tenant_id == tenant.id, Student.is_active == True).first()
        if first_emp:
            demo_users.append({
                "role": "EMPLOYEE",
                "role_label": "Employee",
                "username": first_emp.roll_number or str(first_emp.id),
                "full_name": first_emp.name,
                "icon": "fa-id-badge",
            })
    else:
        teacher = db.query(User).filter(User.tenant_id == tenant.id, User.role == "TEACHER", User.is_active == True).first()
        if teacher:
            demo_users.append({
                "role": "TEACHER",
                "role_label": "Teacher",
                "username": teacher.username,
                "full_name": teacher.full_name,
                "icon": "fa-chalkboard-user",
            })
        student = db.query(User).filter(User.tenant_id == tenant.id, User.role == "STUDENT", User.is_active == True).first()
        if student:
            demo_users.append({
                "role": "STUDENT",
                "role_label": "Student",
                "username": student.username,
                "full_name": student.full_name,
                "icon": "fa-user-graduate",
            })

    branding = tenant.branding.to_dict() if tenant.branding else {
        "institution_name": tenant.name,
        "primary_accent_color": "#c2410c",
        "header_badge_text": "Enterprise Hub" if is_corporate else "Campus Hub",
    }

    return {
        "status": "success",
        "tenant": tenant.to_dict(),
        "tenant_type": t_type,
        "is_corporate": is_corporate,
        "roles": roles,
        "branding": branding,
        "demo_users": demo_users,
    }


@router.post("/login")
def login(
    payload: LoginRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Authenticates a user with username & password.
    Supports global SUPER_ADMIN as well as tenant-scoped TENANT_ADMIN, TEACHER, STUDENT, EMPLOYEE.
    """
    username_clean = payload.username.strip().lower()
    
    # Check if Super Admin
    user = db.query(User).filter(User.username == username_clean, User.role == "SUPER_ADMIN", User.is_active == True).first()
    
    if not user:
        # Search by tenant-scoped username
        tenant_id = payload.tenant_id or 1
        query = db.query(User).filter(
            User.username == username_clean,
            User.tenant_id == tenant_id,
            User.is_active == True,
        )
        if payload.role:
            role_clean = payload.role.strip().upper()
            user = query.filter(User.role == role_clean).first()
        if not user:
            user = query.first()

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
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Logs out user by clearing session cookies and returning the tenant-scoped redirect URL.
    - Super Admin -> /super-admin/login
    - Organization User -> /portal/{tenant_slug}
    - Fallback -> /login
    """
    active_role = request.cookies.get("active_role", "").strip().upper()
    active_tenant_id_str = request.cookies.get("active_tenant_id", "").strip()
    redirect_url = "/login"

    # Also check JWT payload if cookie wasn't present
    auth_token = request.cookies.get("access_token")
    if auth_token:
        try:
            payload = decode_access_token(auth_token)
            if payload:
                if not active_role and payload.get("role"):
                    active_role = payload.get("role", "").upper()
                if not active_tenant_id_str and payload.get("tenant_id"):
                    active_tenant_id_str = str(payload.get("tenant_id"))
        except Exception:
            pass

    if active_role == "SUPER_ADMIN":
        redirect_url = "/super-admin/login"
    elif active_tenant_id_str:
        try:
            t_id = int(active_tenant_id_str)
            tenant = db.query(Tenant).filter(Tenant.id == t_id).first()
            if tenant and tenant.slug:
                redirect_url = f"/login/{tenant.slug}"
        except Exception:
            pass

    # Clear all session cookies
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("active_role", path="/")
    response.delete_cookie("active_tenant_id", path="/")

    return {
        "status": "success",
        "message": "Logged out successfully.",
        "redirect_url": redirect_url,
    }


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
