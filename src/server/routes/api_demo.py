"""
Free Demo Self-Service Provisioning API with AWS SES SMTP Integration.
Provides OTP generation, verification, and automated 7-day Pro Edition corporate tenant provisioning.
"""

import re
import time
import uuid
import secrets
import logging
from datetime import timedelta
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from src.database.session import (
    get_db,
    seed_default_leave_types,
    seed_default_salary_components,
)
from src.database.models import (
    Tenant,
    SystemBranding,
    User,
    AuditLog,
    WorkShift,
    CompanyLocation,
    DesignationMaster,
    Department,
)
from src.utils.auth_utils import hash_password, verify_password
from src.server.rbac_middleware import create_access_token
from src.utils.timezone import get_ist_now
from src.utils.email import send_otp_email, send_demo_welcome_email

logger = logging.getLogger("api_demo")

router = APIRouter(prefix="/api/v1/demo", tags=["Free Demo Self-Service"])

# In-memory OTP store: email.lower() -> {otp_hash, name, company_name, mobile, created_at, attempts}
_OTP_STORE: Dict[str, Dict[str, Any]] = {}

# In-memory Rate Limiter: key -> list of float timestamps
# Keyed by both ip:client_ip and email:client_email
_RATE_LIMIT_STORE: Dict[str, List[float]] = {}

MAX_OTP_PER_WINDOW = 3
RATE_WINDOW_SECONDS = 600  # 10 minutes
OTP_TTL_SECONDS = 600      # 10 minutes
MAX_OTP_ATTEMPTS = 5


def _is_rate_limited(key: str) -> bool:
    """Checks if key (IP or email) has exceeded max OTP requests within window."""
    now = time.time()
    cutoff = now - RATE_WINDOW_SECONDS
    history = _RATE_LIMIT_STORE.get(key, [])
    # Prune old timestamps
    history = [t for t in history if t > cutoff]
    _RATE_LIMIT_STORE[key] = history
    return len(history) >= MAX_OTP_PER_WINDOW


def _record_rate_hit(key: str):
    now = time.time()
    _RATE_LIMIT_STORE.setdefault(key, []).append(now)


EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


# =========================================================================
# Request & Response Schemas
# =========================================================================
class DemoOtpRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    company_name: str = Field(..., min_length=2, max_length=120)
    mobile: str = Field(..., min_length=7, max_length=20)
    email: str = Field(..., min_length=5, max_length=150)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v_clean = v.strip().lower()
        if not EMAIL_REGEX.match(v_clean):
            raise ValueError("Invalid email address format")
        return v_clean


class DemoVerifyRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=150)
    otp: str = Field(..., min_length=4, max_length=10)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v_clean = v.strip().lower()
        if not EMAIL_REGEX.match(v_clean):
            raise ValueError("Invalid email address format")
        return v_clean


def _generate_clean_slug(company_name: str, db: Session) -> str:
    """Generates an alphanumeric URL slug for the tenant with collision avoidance."""
    clean = re.sub(r"[^a-zA-Z0-9]+", "-", company_name).strip("-").lower()
    base_slug = clean[:32] if clean else "demo-company"
    slug = base_slug

    suffix = 1
    while True:
        exists = db.query(Tenant).filter(Tenant.slug == slug).first()
        if not exists:
            return slug
        suffix_str = secrets.token_hex(2)
        slug = f"{base_slug[:28]}-{suffix_str}"
        suffix += 1


# =========================================================================
# Endpoints
# =========================================================================
@router.post("/request-otp")
def request_demo_otp(payload: DemoOtpRequest, request: Request):
    """
    Validates user contact info, generates a 6-digit OTP, and dispatches it via AWS SES SMTP.
    Enforces anti-abuse rate limits on both client IP and email.
    """
    client_ip = request.client.host if request.client else "unknown"
    clean_email = payload.email.strip().lower()
    clean_name = payload.name.strip()
    clean_company = payload.company_name.strip()
    clean_mobile = payload.mobile.strip()

    ip_key = f"ip:{client_ip}"
    email_key = f"email:{clean_email}"

    if _is_rate_limited(ip_key) or _is_rate_limited(email_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many demo requests. Please wait a few minutes before trying again.",
        )

    # Generate 6-digit cryptographic OTP
    otp_code = f"{secrets.randbelow(900000) + 100000}"
    otp_hash = hash_password(otp_code)

    _OTP_STORE[clean_email] = {
        "otp_hash": otp_hash,
        "name": clean_name,
        "company_name": clean_company,
        "mobile": clean_mobile,
        "created_at": time.time(),
        "attempts": 0,
    }

    _record_rate_hit(ip_key)
    _record_rate_hit(email_key)

    # Dispatch OTP via AWS SES
    email_sent = send_otp_email(to_email=clean_email, recipient_name=clean_name, otp_code=otp_code)
    if not email_sent:
        logger.warning(f"AWS SES SMTP dispatch returned false for {clean_email}. Stored OTP in memory.")

    return {
        "status": "success",
        "message": f"A 6-digit verification code has been sent to {clean_email}. It expires in 10 minutes.",
        "email": clean_email,
    }


@router.post("/verify-and-provision")
def verify_otp_and_provision(
    payload: DemoVerifyRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Verifies the submitted 6-digit OTP, programmatically provisions a 7-day Pro Edition
    corporate tenant with complete master structures, seeds initial admin user,
    dispatches credentials email, and sets session cookies for instant seamless access.
    """
    clean_email = payload.email.strip().lower()
    submitted_otp = payload.otp.strip()

    record = _OTP_STORE.get(clean_email)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No verification code found or session expired. Please request a new code.",
        )

    # Check expiration (10 mins)
    if time.time() - record["created_at"] > OTP_TTL_SECONDS:
        _OTP_STORE.pop(clean_email, None)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired. Please request a new code.",
        )

    # Check max failed attempts
    if record["attempts"] >= MAX_OTP_ATTEMPTS:
        _OTP_STORE.pop(clean_email, None)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Too many invalid verification attempts. Please request a new code.",
        )

    # Verify password hash of OTP
    if not verify_password(submitted_otp, record["otp_hash"]):
        record["attempts"] += 1
        remaining = MAX_OTP_ATTEMPTS - record["attempts"]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid verification code. {remaining} attempt(s) remaining.",
        )

    # OTP is verified successfully! Proceed to automated tenant provisioning
    name = record["name"]
    company_name = record["company_name"]
    mobile = record["mobile"]

    # 1. Create Tenant (Corporate, Pro Plan, 7-day trial)
    tenant_slug = _generate_clean_slug(company_name, db)
    now_ist = get_ist_now()
    expires_at = now_ist + timedelta(days=7)

    tenant_uuid = str(uuid.uuid4())
    admin_token = secrets.token_urlsafe(32)
    onboarding_token = secrets.token_urlsafe(32)
    attendance_slug = secrets.token_urlsafe(24)

    new_tenant = Tenant(
        uuid=tenant_uuid,
        slug=tenant_slug,
        name=company_name,
        contact_email=clean_email,
        is_active=True,
        is_deleted=False,
        tenant_type="corporate",
        subscription_plan="PRO",
        subscription_status="ACTIVE",
        subscription_expires_at=expires_at,
        max_face_encodings=500,
        max_nodes=10,
        admin_token=admin_token,
        onboarding_token=onboarding_token,
        attendance_slug=attendance_slug,
    )
    db.add(new_tenant)
    db.flush()

    # 2. Create System Branding (Corporate Hub, Royal Blue Accent)
    branding = SystemBranding(
        tenant_id=new_tenant.id,
        institution_name=company_name,
        short_code=tenant_slug[:10].upper(),
        tagline=f"Face Recognition Employee Management - {company_name}",
        primary_accent_color="#2563eb",
        header_badge_text="Corporate Hub",
        cooldown_minutes=60,
        enable_anti_spoofing=False,
        liveness_mode="off",
        enable_self_attendance=True,
    )
    db.add(branding)

    # 3. Seed Corporate Master Structures
    # Work Shifts
    default_shifts = [
        WorkShift(
            tenant_id=new_tenant.id,
            name="General Shift",
            code="GEN",
            start_time="09:00",
            end_time="18:00",
            grace_period_minutes=15,
            break_duration_minutes=60,
            half_day_hours=4.0,
            is_default=True,
            is_active=True,
        ),
        WorkShift(
            tenant_id=new_tenant.id,
            name="Morning Shift",
            code="MORN",
            start_time="08:00",
            end_time="17:00",
            grace_period_minutes=15,
            break_duration_minutes=60,
            half_day_hours=4.0,
            is_default=False,
            is_active=True,
        ),
        WorkShift(
            tenant_id=new_tenant.id,
            name="Evening Shift",
            code="EVE",
            start_time="14:00",
            end_time="23:00",
            grace_period_minutes=15,
            break_duration_minutes=60,
            half_day_hours=4.0,
            is_default=False,
            is_active=True,
        ),
    ]
    for s in default_shifts:
        db.add(s)

    # Primary Branch Location
    primary_location = CompanyLocation(
        tenant_id=new_tenant.id,
        name="Main Branch / Head Office",
        code="HQ",
        city="Ahmedabad",
        state="Gujarat",
        address="Commercial Center",
        contact_number=mobile,
        is_active=True,
    )
    db.add(primary_location)

    # Core Departments
    default_depts = ["Operations", "Sales & Marketing", "Human Resources", "Finance & Accounts", "Engineering"]
    for d_name in default_depts:
        db.add(Department(
            tenant_id=new_tenant.id,
            name=d_name,
            code=d_name[:4].upper().replace("&", "").strip(),
        ))

    # Core Designations
    default_desigs = ["Director / Managing Partner", "General Manager", "Team Lead / Supervisor", "Senior Executive", "Executive / Staff", "Intern / Trainee"]
    for desig_title in default_desigs:
        db.add(DesignationMaster(
            tenant_id=new_tenant.id,
            title=desig_title,
            code=desig_title[:4].upper(),
            is_active=True,
        ))

    # Master Leave Types & Indian Salary Components
    seed_default_leave_types(db, new_tenant.id)
    seed_default_salary_components(db, new_tenant.id)

    # 4. Create Initial Administrator User
    raw_admin_password = secrets.token_urlsafe(8)
    admin_username = f"admin_{tenant_slug[:12]}"
    # Ensure username is unique
    user_check = db.query(User).filter(User.username == admin_username, User.tenant_id == new_tenant.id).first()
    if user_check:
        admin_username = f"admin_{secrets.token_hex(3)}"

    admin_user = User(
        tenant_id=new_tenant.id,
        username=admin_username,
        email=clean_email,
        password_hash=hash_password(raw_admin_password),
        role="TENANT_ADMIN",
        full_name=name,
        phone_number=mobile,
        is_active=True,
        last_login_at=now_ist,
    )
    db.add(admin_user)

    # 5. Audit Log Entry
    audit = AuditLog(
        tenant_id=new_tenant.id,
        user_id=None,
        actor_name=name,
        actor_role="SELF_SERVICE_REGISTRATION",
        action_type="DEMO_TENANT_PROVISIONED",
        target_type="TENANT",
        target_id=str(new_tenant.id),
        description=f"Self-service Free Demo provisioned: '{company_name}' ({tenant_slug}) on PRO Edition (7-day trial).",
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    db.commit()

    # Clear OTP entry from cache
    _OTP_STORE.pop(clean_email, None)

    # 6. Generate Portal URLs
    base_host = request.headers.get("host") or "localhost:8000"
    scheme = "https" if "curiosityhub.co.in" in base_host else request.url.scheme
    portal_direct_url = f"{scheme}://{base_host}/portal/{new_tenant.slug}"
    expires_str = expires_at.strftime("%d-%b-%Y %I:%M %p IST")

    # 7. Dispatch Welcome Credentials Email
    try:
        send_demo_welcome_email(
            to_email=clean_email,
            recipient_name=name,
            company_name=company_name,
            portal_url=portal_direct_url,
            username=admin_username,
            password=raw_admin_password,
            expires_at_str=expires_str,
        )
    except Exception as e:
        logger.warning(f"Error dispatching welcome credentials email: {e}")

    # 8. Create Access Token & Set Authentication Cookies for Instant Seamless Access
    token = create_access_token(
        user_id=admin_user.id,
        role=admin_user.role,
        tenant_id=new_tenant.id,
        username=admin_user.username,
    )

    response.set_cookie("access_token", token, httponly=True, max_age=86400, path="/")
    response.set_cookie("active_role", admin_user.role, httponly=False, max_age=86400, path="/")
    response.set_cookie("active_tenant_id", str(new_tenant.id), httponly=False, max_age=86400, path="/")

    return {
        "status": "success",
        "message": f"Welcome to Curiosity HUB! Your 7-day Pro Edition demo portal for '{company_name}' is live.",
        "tenant": {
            "id": new_tenant.id,
            "slug": new_tenant.slug,
            "name": new_tenant.name,
            "edition": "PRO",
            "expires_at": expires_str,
        },
        "credentials": {
            "username": admin_username,
            "password": raw_admin_password,
        },
        "portal_url": f"/portal/{new_tenant.slug}",
        "redirect_url": "/dashboard",
    }
