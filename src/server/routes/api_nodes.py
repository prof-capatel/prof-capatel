import logging
import time
from typing import Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Depends
from sqlalchemy.orm import Session

from src.core.camera_utils import decode_image_bytes
from src.core.face_engine import face_engine
from src.core.attendance_manager import attendance_manager
from src.database.models import NodeDevice, Tenant
from src.database.session import get_db
from src.server.tenant_middleware import get_current_tenant, resolve_tenant
from src.server.rbac_middleware import check_tenant_operational_access

logger = logging.getLogger("api_nodes")

router = APIRouter(prefix="/api/v1/nodes", tags=["Edge Nodes Ingestion"])


@router.post("/frame")
async def ingest_node_frame(
    node_id: str = Form("NODE-CLASSROOM-101"),
    location: Optional[str] = Form("Classroom 101"),
    tenant_id: Optional[str] = Form(None),
    is_single_shot: Optional[bool] = Form(False),
    frame: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """
    Primary ingestion endpoint for edge nodes (e.g. Raspberry Pi Zero / Mobile node).
    Receives JPEG compressed frame, detects & recognizes faces scoped to tenant,
    and updates attendance records if cooldown threshold has elapsed.
    """
    start_time = time.time()

    # Resolve target tenant (form override > header/cookie default)
    target_tenant = current_tenant
    if tenant_id:
        custom_tenant = resolve_tenant(db, tenant_id)
        if custom_tenant:
            target_tenant = custom_tenant

    active_tenant_id = target_tenant.id

    # Enforce Tenant Subscription & Operational Status (Suspended/Deleted lockout)
    check_tenant_operational_access(target_tenant)

    # 1. Read & decode image bytes
    contents = await frame.read()
    image_bgr = decode_image_bytes(contents)
    if image_bgr is None:
        raise HTTPException(status_code=400, detail="Invalid image data received.")

    # 2. Record node heartbeat for this tenant
    attendance_manager.record_node_heartbeat(
        node_id=node_id,
        location=location or "Classroom",
        tenant_id=active_tenant_id,
    )

    # 3. Detect and recognize faces (strictly partitioned to this tenant)
    custom_temp_frames = None
    enable_anti_spoof = True
    if target_tenant.branding:
        if target_tenant.branding.temporal_frames_required:
            custom_temp_frames = target_tenant.branding.temporal_frames_required
        if target_tenant.branding.enable_anti_spoofing is not None:
            enable_anti_spoof = bool(target_tenant.branding.enable_anti_spoofing)
        if target_tenant.branding.liveness_mode == "DISABLED":
            enable_anti_spoof = False

    try:
        detections = face_engine.detect_and_recognize_faces(
            image_bgr,
            node_id=node_id,
            tenant_id=active_tenant_id,
            custom_temporal_frames=custom_temp_frames,
            is_single_shot=bool(is_single_shot),
            enable_anti_spoofing=enable_anti_spoof,
        )
    except Exception as e:
        logger.error(f"Face recognition error on node '{node_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Face recognition error: {str(e)}")

    # Compute active tenant cooldown in seconds
    custom_cooldown_secs = None
    if target_tenant.branding and target_tenant.branding.cooldown_minutes is not None:
        custom_cooldown_secs = max(60, int(target_tenant.branding.cooldown_minutes * 60))

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
        cooldown_active = False
        cooldown_remaining_mins = 0
        cooldown_remaining_secs = 0
        log_record = None

        if is_match and student_id is not None:
            if is_live and temporal_confirmed:
                mark_res = attendance_manager.mark_attendance(
                    student_id=student_id,
                    node_id=node_id,
                    confidence_distance=confidence_dist,
                    frame_bgr=image_bgr,
                    face_box=face_box,
                    tenant_id=active_tenant_id,
                    custom_cooldown_seconds=custom_cooldown_secs,
                )
                if mark_res:
                    attendance_logged = mark_res.get("attendance_logged", False)
                    cooldown_active = mark_res.get("cooldown_active", False)
                    cooldown_remaining_mins = mark_res.get("cooldown_remaining_minutes", 0)
                    cooldown_remaining_secs = mark_res.get("cooldown_remaining_seconds", 0)
                    log_record = mark_res.get("record") or mark_res.get("log_data")
            else:
                # Spoof detected - log security warning
                attendance_manager.record_spoof_event(
                    node_id=node_id,
                    student_name=det.get("name"),
                    reasons=liveness_reasons,
                    tenant_id=active_tenant_id,
                )

        processed_detections.append({
            "tenant_id": active_tenant_id,
            "student_id": student_id,
            "name": det.get("name"),
            "roll_number": det.get("roll_number"),
            "department": det.get("department"),
            "user_role": det.get("user_role", "student"),
            "closest_candidate_name": det.get("closest_candidate_name"),
            "closest_candidate_roll": det.get("closest_candidate_roll"),
            "distance": confidence_dist,
            "threshold": det.get("threshold", 0.55),
            "confidence_pct": det.get("confidence_pct", 0.0),
            "is_match": is_match,
            "is_live": is_live,
            "liveness_score": liveness_score,
            "liveness_status": liveness_status,
            "temporal_confirmed": temporal_confirmed,
            "temporal_status": temporal_status,
            "temporal_frames": temporal_frames,
            "liveness_reasons": liveness_reasons,
            "attendance_logged": attendance_logged,
            "cooldown_active": cooldown_active,
            "cooldown_remaining_minutes": cooldown_remaining_mins,
            "cooldown_remaining_seconds": cooldown_remaining_secs,
            "log_data": log_record,
            "box": face_box,
        })

    elapsed_ms = round((time.time() - start_time) * 1000, 1)

    return {
        "status": "success",
        "tenant_id": active_tenant_id,
        "node_id": node_id,
        "processing_time_ms": elapsed_ms,
        "faces_detected": len(processed_detections),
        "detections": processed_detections,
        "results": processed_detections,
    }


@router.post("/demo-frame")
async def demo_visual_recognition_frame(
    node_id: str = Form("NODE-DEMO-VIEWER"),
    tenant_id: Optional[str] = Form(None),
    is_single_shot: Optional[bool] = Form(False),
    frame: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """
    Dedicated Non-Logging Visual Recognition Testing Endpoint.
    Executes full face detection, vector matching, confidence calculation, and anti-spoofing diagnostics,
    but STRICTLY BYPASSES any database logging, attendance record creation, or cooldown deduplication locks.
    """
    start_time = time.time()

    target_tenant = current_tenant
    if tenant_id:
        custom_tenant = resolve_tenant(db, tenant_id)
        if custom_tenant:
            target_tenant = custom_tenant

    active_tenant_id = target_tenant.id

    # 1. Read & decode image bytes with auto EXIF orientation transpose
    contents = await frame.read()
    image_bgr = decode_image_bytes(contents)
    if image_bgr is None:
        raise HTTPException(status_code=400, detail="Invalid image data received.")

    # 2. Detect & recognize faces without writing to database
    custom_temp_frames = None
    enable_anti_spoof = True
    if target_tenant.branding:
        if target_tenant.branding.temporal_frames_required:
            custom_temp_frames = target_tenant.branding.temporal_frames_required
        if target_tenant.branding.enable_anti_spoofing is not None:
            enable_anti_spoof = bool(target_tenant.branding.enable_anti_spoofing)
        if target_tenant.branding.liveness_mode == "DISABLED":
            enable_anti_spoof = False

    try:
        detections = face_engine.detect_and_recognize_faces(
            image_bgr,
            node_id=node_id,
            tenant_id=active_tenant_id,
            custom_temporal_frames=custom_temp_frames,
            is_single_shot=bool(is_single_shot),
            enable_anti_spoofing=enable_anti_spoof,
        )
    except Exception as e:
        logger.error(f"Face recognition demo error on node '{node_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Face recognition error: {str(e)}")

    demo_detections = []
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

        demo_detections.append({
            "tenant_id": active_tenant_id,
            "student_id": student_id,
            "name": det.get("name"),
            "roll_number": det.get("roll_number"),
            "department": det.get("department"),
            "user_role": det.get("user_role", "student"),
            "closest_candidate_name": det.get("closest_candidate_name"),
            "closest_candidate_roll": det.get("closest_candidate_roll"),
            "distance": confidence_dist,
            "threshold": det.get("threshold", 0.55),
            "confidence_pct": det.get("confidence_pct", 0.0),
            "is_match": is_match,
            "is_live": is_live,
            "liveness_score": liveness_score,
            "liveness_status": liveness_status,
            "temporal_confirmed": temporal_confirmed,
            "temporal_status": temporal_status,
            "temporal_frames": temporal_frames,
            "liveness_reasons": liveness_reasons,
            "attendance_logged": False,  # Strict bypass for demo testing
            "demo_mode": True,
            "box": face_box,
        })

    elapsed_ms = round((time.time() - start_time) * 1000, 1)

    return {
        "status": "success",
        "demo_mode": True,
        "tenant_id": active_tenant_id,
        "node_id": node_id,
        "processing_time_ms": elapsed_ms,
        "faces_detected": len(demo_detections),
        "detections": demo_detections,
        "results": demo_detections,
    }


@router.get("")
def list_nodes(
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Lists all registered edge nodes for current tenant."""
    nodes = db.query(NodeDevice).filter(NodeDevice.tenant_id == current_tenant.id).all()
    return {
        "tenant_id": current_tenant.id,
        "nodes": [n.to_dict() for n in nodes],
    }
