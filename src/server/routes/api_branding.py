import os
import time
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.config import BRANDING_DIR
from src.database.models import SystemBranding
from src.database.session import get_db

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


def get_or_create_branding(db: Session) -> SystemBranding:
    """Helper to fetch singleton branding record or create default."""
    branding = db.query(SystemBranding).filter(SystemBranding.id == 1).first()
    if not branding:
        branding = SystemBranding(
            id=1,
            institution_name="FaceAttendance Campus",
            short_code="FA-HUB",
            tagline="Raspberry Pi Zero Edge Nodes & Central Face Recognition",
            primary_accent_color="#6366f1",
            header_badge_text="Thin-Client Hub",
        )
        db.add(branding)
        db.commit()
        db.refresh(branding)
    return branding


@router.get("")
def get_branding(db: Session = Depends(get_db)):
    """Retrieves current institutional branding settings."""
    branding = get_or_create_branding(db)
    return {
        "status": "success",
        "branding": branding.to_dict(),
    }


@router.post("")
def update_branding(payload: BrandingUpdateRequest, db: Session = Depends(get_db)):
    """Updates institutional white-labeling text, acronym, and color accents."""
    branding = get_or_create_branding(db)

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

    db.commit()
    db.refresh(branding)

    return {
        "status": "success",
        "message": "Institutional branding updated successfully.",
        "branding": branding.to_dict(),
    }


@router.post("/logo")
async def upload_branding_logo(logo: UploadFile = File(...), db: Session = Depends(get_db)):
    """Uploads and saves an institutional logo image to filesystem storage."""
    branding = get_or_create_branding(db)

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

    # Save new file
    safe_filename = f"inst_logo_{int(time.time())}{ext}"
    target_path = BRANDING_DIR / safe_filename
    with open(target_path, "wb") as f:
        f.write(file_bytes)

    branding.logo_filename = safe_filename
    db.commit()
    db.refresh(branding)

    return {
        "status": "success",
        "message": "Institute logo uploaded and updated successfully.",
        "branding": branding.to_dict(),
    }


@router.delete("/logo")
def delete_branding_logo(db: Session = Depends(get_db)):
    """Resets the institutional logo to default system icon."""
    branding = get_or_create_branding(db)

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
        "branding": branding.to_dict(),
    }
