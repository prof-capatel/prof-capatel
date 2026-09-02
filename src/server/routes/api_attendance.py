import asyncio
from datetime import datetime, date, time as dt_time
import io
import json
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct

from src.config import EXPORTS_DIR
from src.core.attendance_manager import attendance_manager
from src.database.models import AttendanceRecord, Student, NodeDevice
from src.database.session import get_db

router = APIRouter(prefix="/api/v1/attendance", tags=["Attendance Management"])


@router.get("/records")
def get_attendance_records(
    date_str: Optional[str] = Query(None, description="Date filter YYYY-MM-DD"),
    roll_number: Optional[str] = Query(None, description="Filter by student roll number"),
    node_id: Optional[str] = Query(None, description="Filter by node ID"),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Retrieves paginated and filtered attendance records."""
    query = db.query(AttendanceRecord).join(Student, AttendanceRecord.student_id == Student.id, isouter=True)

    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            start_dt = datetime.combine(target_date, dt_time.min)
            end_dt = datetime.combine(target_date, dt_time.max)
            query = query.filter(AttendanceRecord.timestamp.between(start_dt, end_dt))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    if roll_number:
        query = query.filter(Student.roll_number.ilike(f"%{roll_number.strip()}%"))

    if node_id:
        query = query.filter(AttendanceRecord.node_id == node_id)

    records = query.order_by(AttendanceRecord.timestamp.desc()).limit(limit).all()
    return {"records": [r.to_dict() for r in records]}


@router.get("/stats")
def get_attendance_stats(db: Session = Depends(get_db)):
    """Computes summary statistics for the dashboard cards."""
    today = date.today()
    start_today = datetime.combine(today, dt_time.min)
    end_today = datetime.combine(today, dt_time.max)

    total_students = db.query(Student).filter(Student.is_active == True).count()
    
    # Count unique students present today
    present_today = (
        db.query(distinct(AttendanceRecord.student_id))
        .filter(AttendanceRecord.timestamp.between(start_today, end_today))
        .filter(AttendanceRecord.student_id != None)
        .count()
    )

    total_today_logs = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.timestamp.between(start_today, end_today))
        .count()
    )

    active_nodes = (
        db.query(NodeDevice)
        .filter(NodeDevice.is_online == True)
        .count()
    )

    attendance_pct = round((present_today / total_students * 100), 1) if total_students > 0 else 0.0

    return {
        "total_students": total_students,
        "present_today": present_today,
        "attendance_percentage": attendance_pct,
        "total_today_logs": total_today_logs,
        "active_nodes": active_nodes,
        "date": today.isoformat(),
    }


@router.get("/export")
def export_attendance_report(
    date_str: Optional[str] = Query(None, description="Filter date YYYY-MM-DD"),
    export_format: str = Query("csv", pattern="^(csv|xlsx)$"),
    db: Session = Depends(get_db),
):
    """Exports attendance history into downloadable CSV or Excel spreadsheet."""
    query = (
        db.query(
            AttendanceRecord.id,
            Student.roll_number,
            Student.name,
            Student.department,
            AttendanceRecord.node_id,
            AttendanceRecord.timestamp,
            AttendanceRecord.confidence_distance,
            AttendanceRecord.status,
        )
        .join(Student, AttendanceRecord.student_id == Student.id, isouter=True)
        .order_by(AttendanceRecord.timestamp.desc())
    )

    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            start_dt = datetime.combine(target_date, dt_time.min)
            end_dt = datetime.combine(target_date, dt_time.max)
            query = query.filter(AttendanceRecord.timestamp.between(start_dt, end_dt))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    results = query.all()

    # Convert to pandas DataFrame
    data = []
    for row in results:
        data.append({
            "Log ID": row[0],
            "Roll Number": row[1] or "N/A",
            "Student Name": row[2] or "Unknown",
            "Department": row[3] or "N/A",
            "Node Location": row[4],
            "Timestamp": row[5].strftime("%Y-%m-%d %H:%M:%S") if row[5] else "",
            "Confidence Distance": round(row[6], 4) if row[6] is not None else "",
            "Status": row[7],
        })

    df = pd.DataFrame(data)
    date_label = date_str or datetime.now().strftime("%Y%m%d")

    if export_format == "csv":
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)
        return StreamingResponse(
            io.BytesIO(csv_buffer.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=attendance_report_{date_label}.csv"},
        )
    else:
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Attendance")
        excel_buffer.seek(0)
        return StreamingResponse(
            excel_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=attendance_report_{date_label}.xlsx"},
        )


@router.get("/live-stream")
async def live_stream_events():
    """
    Server-Sent Events (SSE) streaming endpoint for real-time live attendance feed
    in the web dashboard.
    """
    queue = attendance_manager.subscribe()

    async def event_generator():
        try:
            # Send initial keepalive
            yield f"data: {json.dumps({'type': 'CONNECTED', 'message': 'Live stream connected.'})}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Send heartbeat ping to keep connection alive
                    yield f": ping\n\n"
        finally:
            attendance_manager.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
