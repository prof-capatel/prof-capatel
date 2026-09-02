from datetime import date
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from src.database.models import Student, AttendanceRecord, NodeDevice, SystemBranding
from src.database.session import get_db

templates = Jinja2Templates(directory="src/server/templates")

router = APIRouter(include_in_schema=False)


def get_branding_dict(db: Session) -> dict:
    """Helper to load institutional branding for template injection."""
    branding = db.query(SystemBranding).filter(SystemBranding.id == 1).first()
    if branding:
        return branding.to_dict()
    return {
        "id": 1,
        "institution_name": "FaceAttendance Campus",
        "short_code": "FA-HUB",
        "tagline": "Raspberry Pi Zero Edge Nodes & Central Face Recognition",
        "logo_filename": None,
        "logo_url": None,
        "primary_accent_color": "#6366f1",
        "header_badge_text": "Thin-Client Hub",
        "contact_email": None,
    }


@router.get("/", response_class=HTMLResponse)
def page_dashboard(request: Request, db: Session = Depends(get_db)):
    """Main Admin Overview Dashboard."""
    total_students = db.query(Student).filter(Student.is_active == True).count()
    recent_logs = (
        db.query(AttendanceRecord)
        .order_by(AttendanceRecord.timestamp.desc())
        .limit(10)
        .all()
    )
    nodes = db.query(NodeDevice).all()
    branding = get_branding_dict(db)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "page_title": "Live Overview",
            "active_page": "dashboard",
            "total_students": total_students,
            "recent_logs": [r.to_dict() for r in recent_logs],
            "nodes": [n.to_dict() for n in nodes],
            "branding": branding,
        },
    )


@router.get("/students", response_class=HTMLResponse)
def page_students(request: Request, db: Session = Depends(get_db)):
    """Student Directory & Face Profile Management."""
    students = db.query(Student).order_by(Student.name.asc()).all()
    branding = get_branding_dict(db)
    return templates.TemplateResponse(
        "students.html",
        {
            "request": request,
            "page_title": "Student Directory",
            "active_page": "students",
            "students": [s.to_dict() for s in students],
            "branding": branding,
        },
    )


@router.get("/enroll", response_class=HTMLResponse)
def page_enroll(request: Request, db: Session = Depends(get_db)):
    """Interactive Browser & Guided Face Enrollment."""
    branding = get_branding_dict(db)
    return templates.TemplateResponse(
        "enroll.html",
        {
            "request": request,
            "page_title": "Enroll New Student",
            "active_page": "enroll",
            "branding": branding,
        },
    )


@router.get("/logs", response_class=HTMLResponse)
def page_logs(request: Request, db: Session = Depends(get_db)):
    """Full Attendance Log Audit & Export."""
    today_str = date.today().isoformat()
    branding = get_branding_dict(db)
    return templates.TemplateResponse(
        "logs.html",
        {
            "request": request,
            "page_title": "Attendance Logs",
            "active_page": "logs",
            "today_str": today_str,
            "branding": branding,
        },
    )


@router.get("/nodes", response_class=HTMLResponse)
def page_nodes(request: Request, db: Session = Depends(get_db)):
    """Connected Edge Nodes / Pi Zero Monitor."""
    nodes = db.query(NodeDevice).all()
    branding = get_branding_dict(db)
    return templates.TemplateResponse(
        "nodes.html",
        {
            "request": request,
            "page_title": "Edge Nodes Monitor",
            "active_page": "nodes",
            "nodes": [n.to_dict() for n in nodes],
            "branding": branding,
        },
    )


@router.get("/analytics", response_class=HTMLResponse)
def page_analytics(request: Request, db: Session = Depends(get_db)):
    """Institutional Attendance Analytics & Defaulter Reports."""
    branding = get_branding_dict(db)
    return templates.TemplateResponse(
        "analytics.html",
        {
            "request": request,
            "page_title": "Attendance Analytics & Reports",
            "active_page": "analytics",
            "branding": branding,
        },
    )


@router.get("/settings", response_class=HTMLResponse)
def page_settings(request: Request, db: Session = Depends(get_db)):
    """Visual Theme Engine & System Preferences Settings."""
    branding = get_branding_dict(db)
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "page_title": "System Settings & Theme",
            "active_page": "settings",
            "branding": branding,
        },
    )


@router.get("/mobile-capture", response_class=HTMLResponse)
def page_mobile_capture(request: Request, db: Session = Depends(get_db)):
    """Dedicated Mobile Browser Attendance Node."""
    branding = get_branding_dict(db)
    return templates.TemplateResponse(
        "mobile_capture.html",
        {
            "request": request,
            "page_title": "Mobile Capture Node",
            "active_page": "mobile",
            "branding": branding,
        },
    )
