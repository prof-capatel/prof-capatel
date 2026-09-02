from datetime import date
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from src.database.models import Student, AttendanceRecord, NodeDevice
from src.database.session import get_db

templates = Jinja2Templates(directory="src/server/templates")

router = APIRouter(include_in_schema=False)


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

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "page_title": "Live Overview",
            "active_page": "dashboard",
            "total_students": total_students,
            "recent_logs": [r.to_dict() for r in recent_logs],
            "nodes": [n.to_dict() for n in nodes],
        },
    )


@router.get("/students", response_class=HTMLResponse)
def page_students(request: Request, db: Session = Depends(get_db)):
    """Student Directory & Face Profile Management."""
    students = db.query(Student).order_by(Student.name.asc()).all()
    return templates.TemplateResponse(
        "students.html",
        {
            "request": request,
            "page_title": "Student Directory",
            "active_page": "students",
            "students": [s.to_dict() for s in students],
        },
    )


@router.get("/enroll", response_class=HTMLResponse)
def page_enroll(request: Request):
    """Interactive Browser & Guided Face Enrollment."""
    return templates.TemplateResponse(
        "enroll.html",
        {
            "request": request,
            "page_title": "Enroll New Student",
            "active_page": "enroll",
        },
    )


@router.get("/logs", response_class=HTMLResponse)
def page_logs(request: Request, db: Session = Depends(get_db)):
    """Full Attendance Log Audit & Export."""
    today_str = date.today().isoformat()
    return templates.TemplateResponse(
        "logs.html",
        {
            "request": request,
            "page_title": "Attendance Logs",
            "active_page": "logs",
            "today_str": today_str,
        },
    )


@router.get("/nodes", response_class=HTMLResponse)
def page_nodes(request: Request, db: Session = Depends(get_db)):
    """Connected Edge Nodes / Pi Zero Monitor."""
    nodes = db.query(NodeDevice).all()
    return templates.TemplateResponse(
        "nodes.html",
        {
            "request": request,
            "page_title": "Edge Nodes Monitor",
            "active_page": "nodes",
            "nodes": [n.to_dict() for n in nodes],
        },
    )


@router.get("/mobile-capture", response_class=HTMLResponse)
def page_mobile_capture(request: Request):
    """Dedicated Mobile Browser Attendance Node."""
    return templates.TemplateResponse(
        "mobile_capture.html",
        {
            "request": request,
            "page_title": "Mobile Capture Node",
            "active_page": "mobile",
        },
    )

