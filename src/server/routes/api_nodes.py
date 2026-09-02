import time
from typing import Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Depends
from sqlalchemy.orm import Session

from src.core.camera_utils import decode_image_bytes
from src.core.face_engine import face_engine
from src.core.attendance_manager import attendance_manager
from src.database.session import get_db

router = APIRouter(prefix="/api/v1/nodes", tags=["Edge Nodes Ingestion"])


@router.post("/frame")
async def ingest_node_frame(
    node_id: str = Form("NODE-CLASSROOM-101"),
    location: Optional[str] = Form("Classroom 101"),
    frame: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Primary ingestion endpoint for edge nodes (e.g. Raspberry Pi Zero).
    Receives JPEG compressed frame, detects & recognizes all faces,
    and updates attendance records if cooldown threshold has elapsed.
    """
    start_time = time.time()
    
    # 1. Read & decode image bytes
    contents = await frame.read()
    image_bgr = decode_image_bytes(contents)
    if image_bgr is None:
        raise HTTPException(status_code=400, detail="Invalid image data received.")

    # 2. Record node heartbeat
    attendance_manager.record_node_heartbeat(node_id=node_id, location=location)

    # 3. Detect and recognize faces
    try:
        detections = face_engine.detect_and_recognize_faces(image_bgr)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Face recognition error: {str(e)}")

    processed_detections = []
    
    # 4. Process attendance for all detected faces with Anti-Spoofing gating
    for det in detections:
        is_match = det.get("is_match", False)
        student_id = det.get("student_id")
        confidence_dist = det.get("distance", 1.0)
        face_box = det.get("box")

        is_live = det.get("is_live", True)
        liveness_score = det.get("liveness_score", 1.0)
        liveness_status = det.get("liveness_status", "REAL")
        temporal_confirmed = det.get("temporal_confirmed", True)
        temporal_status = det.get("temporal_status", "REAL")
        temporal_frames = det.get("temporal_frames", 1)
        liveness_reasons = det.get("liveness_reasons", [])

        attendance_logged = False
        log_record = None

        if not is_live:
            # Presentation attack / spoof attempt detected -> Block attendance & broadcast alert
            attendance_manager.record_spoof_event(
                node_id=node_id,
                student_name=det.get("name"),
                reasons=liveness_reasons,
            )
        elif is_match and student_id is not None and temporal_confirmed:
            # Real physical presence confirmed -> Mark attendance (cooldown protected)
            log_record = attendance_manager.mark_attendance(
                student_id=student_id,
                node_id=node_id,
                confidence_distance=confidence_dist,
                frame_bgr=image_bgr,
                face_box=face_box,
            )
            if log_record:
                attendance_logged = True

        processed_detections.append({
            "student_id": student_id,
            "name": det.get("name"),
            "roll_number": det.get("roll_number"),
            "department": det.get("department"),
            "distance": det.get("distance"),
            "confidence_pct": det.get("confidence_pct"),
            "is_match": is_match,
            "box": face_box,
            "is_live": is_live,
            "liveness_score": liveness_score,
            "liveness_status": liveness_status,
            "temporal_confirmed": temporal_confirmed,
            "temporal_status": temporal_status,
            "temporal_frames": temporal_frames,
            "liveness_reasons": liveness_reasons,
            "attendance_logged": attendance_logged,
        })

    elapsed_ms = round((time.time() - start_time) * 1000, 2)

    return {
        "status": "success",
        "node_id": node_id,
        "processing_time_ms": elapsed_ms,
        "faces_detected": len(processed_detections),
        "results": processed_detections,
    }


@router.post("/heartbeat")
def node_heartbeat(
    node_id: str = Form(...),
    fps: float = Form(2.0),
    location: str = Form("Classroom"),
):
    """Simple heartbeat ping from edge nodes."""
    attendance_manager.record_node_heartbeat(node_id=node_id, fps=fps, location=location)
    return {"status": "ok", "node_id": node_id}
