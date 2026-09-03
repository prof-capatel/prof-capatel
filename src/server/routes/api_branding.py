import os
import time
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.config import BRANDING_DIR
from src.database.models import SystemBranding, Tenant
from src.database.session import get_db
from src.server.tenant_middleware import get_current_tenant

router = APIRouter(prefix="/api/v1/branding", tags=["Branding & White-Labeling"])

ALLOWED_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".svg", ".webp"}
MAX_LOGO_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


class BrandingUpdateRequest(BaseModel):
    institution_name: str
    short_code: str
    tagline: Optional[str] = None
    primary_accent_color: Optional[str] = "#6366f1"
    header_badge_text: Optional[str] = "Thin-Client Hub"
    contact_email: Optional[str] = None
    cooldown_minutes: Optional[int] = 60
    enable_anti_spoofing: Optional[bool] = True
    liveness_mode: Optional[str] = "BALANCED"
    temporal_frames_required: Optional[int] = 3
    enable_audio_chime: Optional[bool] = True
    enable_haptic_feedback: Optional[bool] = True


def get_or_create_tenant_branding(db: Session, tenant_id: int, tenant_name: str = "FaceAttendance Campus") -> SystemBranding:
    """Helper to fetch singleton branding record for a specific tenant or create default."""
    branding = db.query(SystemBranding).filter(SystemBranding.tenant_id == tenant_id).first()
    if not branding:
        branding = SystemBranding(
            tenant_id=tenant_id,
            institution_name=tenant_name,
            short_code="FA-HUB",
            tagline="Raspberry Pi Zero Edge Nodes & Central Face Recognition",
            primary_accent_color="#6366f1",
            header_badge_text="Thin-Client Hub",
            cooldown_minutes=60,
            enable_anti_spoofing=True,
            liveness_mode="BALANCED",
            temporal_frames_required=3,
            enable_audio_chime=True,
            enable_haptic_feedback=True,
        )
        db.add(branding)
        db.commit()
        db.refresh(branding)
    return branding


@router.get("")
def get_branding(
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Retrieves current institutional branding settings for the active tenant."""
    branding = get_or_create_tenant_branding(db, current_tenant.id, current_tenant.name)
    return {
        "status": "success",
        "tenant_id": current_tenant.id,
        "branding": branding.to_dict(),
    }


@router.post("")
def update_branding(
    payload: BrandingUpdateRequest,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Updates institutional white-labeling text, acronym, color accents, and cooldown window for current tenant."""
    branding = get_or_create_tenant_branding(db, current_tenant.id, current_tenant.name)

    if not payload.institution_name.strip():
        raise HTTPException(status_code=400, detail="Institution name cannot be empty.")
    if not payload.short_code.strip():
        raise HTTPException(status_code=400, detail="Short code / acronym cannot be empty.")

    branding.institution_name = payload.institution_name.strip()
    branding.short_code = payload.short_code.strip().upper()
    branding.tagline = payload.tagline.strip() if payload.tagline else ""
    branding.primary_accent_color = payload.primary_accent_color.strip() if payload.primary_accent_color else "#6366f1"
    branding.header_badge_text = payload.header_badge_text.strip() if payload.header_badge_text else "Thin-Client Hub"
    branding.contact_email = payload.contact_email.strip() if payload.contact_email else None
    
    if payload.cooldown_minutes is not None:
        branding.cooldown_minutes = max(1, min(1440, int(payload.cooldown_minutes)))

    if payload.enable_anti_spoofing is not None:
        branding.enable_anti_spoofing = bool(payload.enable_anti_spoofing)

    if payload.liveness_mode is not None:
        mode = payload.liveness_mode.strip().upper()
        if mode in ["STRICT", "BALANCED", "FAST", "DISABLED"]:
            branding.liveness_mode = mode

    if payload.temporal_frames_required is not None:
        branding.temporal_frames_required = max(1, min(10, int(payload.temporal_frames_required)))

    if payload.enable_audio_chime is not None:
        branding.enable_audio_chime = bool(payload.enable_audio_chime)

    if payload.enable_haptic_feedback is not None:
        branding.enable_haptic_feedback = bool(payload.enable_haptic_feedback)

    # Also sync Tenant name
    current_tenant.name = branding.institution_name

    db.commit()
    db.refresh(branding)

    return {
        "status": "success",
        "message": "Institutional branding updated successfully.",
        "tenant_id": current_tenant.id,
        "branding": branding.to_dict(),
    }


@router.post("/logo")
async def upload_branding_logo(
    logo: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Uploads and saves an institutional logo image to filesystem storage for active tenant."""
    branding = get_or_create_tenant_branding(db, current_tenant.id, current_tenant.name)

    ext = Path(logo.filename or "").suffix.lower()
    if ext not in ALLOWED_LOGO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{ext}'. Allowed formats: {', '.join(ALLOWED_LOGO_EXTENSIONS)}",
        )

    file_bytes = await logo.read()
    if len(file_bytes) > MAX_LOGO_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="Logo file size exceeds maximum limit of 5MB.")
    if len(file_bytes) < 100:
        raise HTTPException(status_code=400, detail="Invalid or empty image file.")

    # Remove previous logo file if existed
    if branding.logo_filename:
        old_file = BRANDING_DIR / branding.logo_filename
        if old_file.exists():
            try:
                old_file.unlink()
            except Exception:
                pass

    # Save new file scoped with tenant id
    safe_filename = f"tenant_{current_tenant.id}_logo_{int(time.time())}{ext}"
    target_path = BRANDING_DIR / safe_filename
    with open(target_path, "wb") as f:
        f.write(file_bytes)

    branding.logo_filename = safe_filename
    db.commit()
    db.refresh(branding)

    return {
        "status": "success",
        "message": "Institute logo uploaded and updated successfully.",
        "tenant_id": current_tenant.id,
        "branding": branding.to_dict(),
    }


@router.delete("/logo")
def delete_branding_logo(
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Resets the institutional logo to default system icon for active tenant."""
    branding = get_or_create_tenant_branding(db, current_tenant.id, current_tenant.name)

    if branding.logo_filename:
        old_file = BRANDING_DIR / branding.logo_filename
        if old_file.exists():
            try:
                old_file.unlink()
            except Exception:
                pass
        branding.logo_filename = None
        db.commit()
        db.refresh(branding)

    return {
        "status": "success",
        "message": "Institute logo reset to default.",
        "tenant_id": current_tenant.id,
        "branding": branding.to_dict(),
    }
