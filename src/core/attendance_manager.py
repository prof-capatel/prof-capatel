import asyncio
from datetime import datetime, timedelta
import logging
from pathlib import Path
import time
from typing import Dict, List, Optional, Tuple, Any
import cv2
import numpy as np
from sqlalchemy.orm import Session

from src.config import (
    SNAPSHOTS_DIR,
    DEDUPLICATION_WINDOW_SECONDS,
    DEFAULT_TENANT_ID,
)
from src.database.models import AttendanceRecord, NodeDevice, Student, SystemBranding, Tenant, WorkShift
from src.database.session import SessionLocal, get_db_context
from src.utils.timezone import get_ist_now, get_ist_date

logger = logging.getLogger("attendance_manager")
logger.setLevel(logging.INFO)


class AttendanceManager:
    """
    Manages campus-wide attendance deduplication and institutional cooldown windows,
    database record persistence, snapshot storage, and real-time live event dispatching.
    """

    def __init__(self, default_cooldown_seconds: int = DEDUPLICATION_WINDOW_SECONDS):
        self.default_cooldown_seconds = default_cooldown_seconds
        # In-memory sliding window cache: (tenant_id, student_id) -> last_logged_timestamp (float)
        self._last_logged_cache: Dict[Tuple[int, int], float] = {}
        # Cached cooldown durations per tenant: tenant_id -> seconds
        self._tenant_cooldown_cache: Dict[int, int] = {}
        # Subscriber queues for real-time live feed (SSE/WebSockets)
        self._subscribers: List[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        """Subscribes an event queue for real-time SSE live updates."""
        queue = asyncio.Queue()
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        """Unsubscribes a listener queue when connection closes."""
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    async def broadcast_event(self, event_data: Dict[str, Any]):
        """Dispatches real-time attendance events to all connected clients."""
        for queue in list(self._subscribers):
            try:
                await queue.put(event_data)
            except Exception as e:
                logger.warning(f"Failed to send event to subscriber: {e}")

    def publish(self, event_data: Dict[str, Any]):
        """Dispatches real-time attendance event synchronously to all subscriber queues."""
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event_data)
            except Exception as e:
                logger.warning(f"Failed to put event in queue: {e}")

    def get_tenant_cooldown_seconds(self, tenant_id: int) -> int:
        """Retrieves configured cooldown window (in seconds) for a tenant from database/cache."""
        if tenant_id in self._tenant_cooldown_cache:
            return self._tenant_cooldown_cache[tenant_id]

        with SessionLocal() as db:
            branding = db.query(SystemBranding).filter(SystemBranding.tenant_id == tenant_id).first()
            if branding and branding.cooldown_minutes:
                cd_seconds = max(60, int(branding.cooldown_minutes * 60))
            else:
                cd_seconds = self.default_cooldown_seconds

            self._tenant_cooldown_cache[tenant_id] = cd_seconds
            return cd_seconds

    def invalidate_cooldown_cache(self, tenant_id: int):
        """Invalidates in-memory cooldown cache when settings are updated."""
        if tenant_id in self._tenant_cooldown_cache:
            del self._tenant_cooldown_cache[tenant_id]

    def should_log_attendance(
        self,
        student_id: int,
        node_id: str,
        tenant_id: int = DEFAULT_TENANT_ID,
        custom_cooldown_seconds: Optional[int] = None,
    ) -> Tuple[bool, int, int]:
        """
        Evaluates campus-wide deduplication cooldown for a student in a tenant.
        Returns: (can_log: bool, remaining_seconds: int, cooldown_seconds: int)
        """
        cooldown_secs = (
            custom_cooldown_seconds
            if custom_cooldown_seconds is not None
            else self.get_tenant_cooldown_seconds(tenant_id)
        )

        key = (tenant_id, student_id)
        current_time = time.time()
        last_time = self._last_logged_cache.get(key)

        # Fallback to MySQL database if not in memory (e.g. server restart)
        if last_time is None:
            with SessionLocal() as db:
                latest_record = (
                    db.query(AttendanceRecord.timestamp)
                    .filter(
                        AttendanceRecord.tenant_id == tenant_id,
                        AttendanceRecord.student_id == student_id,
                    )
                    .order_by(AttendanceRecord.timestamp.desc())
                    .first()
                )
                if latest_record and latest_record[0]:
                    last_time = latest_record[0].timestamp()
                    self._last_logged_cache[key] = last_time

        if last_time is None:
            return True, 0, cooldown_secs

        elapsed = current_time - last_time
        if elapsed >= cooldown_secs:
            return True, 0, cooldown_secs

        remaining = max(1, int(cooldown_secs - elapsed))
        return False, remaining, cooldown_secs

    def _update_node_stats(self, db: Session, tenant_id: int, node_id: str):
        """Updates NodeDevice last heartbeat, online status, and detections count."""
        node = db.query(NodeDevice).filter(
            NodeDevice.tenant_id == tenant_id,
            NodeDevice.node_id == node_id,
        ).first()
        if node:
            node.last_heartbeat = get_ist_now()
            node.is_online = True
            node.total_detections += 1
        else:
            new_node = NodeDevice(
                tenant_id=tenant_id,
                node_id=node_id,
                name=f"Node {node_id}",
                location="Classroom / Gateway",
                last_heartbeat=get_ist_now(),
                is_online=True,
                total_detections=1,
            )
            db.add(new_node)

    def _broadcast_attendance(self, tenant_id: int, log_data: Dict[str, Any]):
        """Dispatches attendance event to async SSE and background worker queues."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.broadcast_event({
                    "type": "ATTENDANCE_LOGGED",
                    "tenant_id": tenant_id,
                    "data": log_data,
                }))
        except RuntimeError:
            pass

        self.publish({
            "type": "ATTENDANCE_LOGGED",
            "tenant_id": tenant_id,
            "data": log_data,
        })

    def mark_attendance(
        self,
        student_id: int,
        node_id: str,
        confidence_distance: float,
        frame_bgr: Optional[np.ndarray] = None,
        face_box: Optional[Dict[str, int]] = None,
        tenant_id: int = DEFAULT_TENANT_ID,
        custom_cooldown_seconds: Optional[int] = None,
        geo_latitude: Optional[float] = None,
        geo_longitude: Optional[float] = None,
        geo_distance_meters: Optional[float] = None,
        is_self_attendance: bool = False,
        now_dt: Optional[datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Processes a recognized face:
        - For Corporate Tenants:
          - Evaluates dual punches (Check-In & Check-Out) for the current calendar day.
          - First punch -> Check-In (evaluates ON_TIME vs LATE_CHECKIN against shift_check_in_time + grace).
          - Subsequent punch -> Check-Out (evaluates EARLY_DEPARTURE vs COMPLETED against shift_check_out_time and computes active hours).
        - For Educational Tenants:
          - Evaluates campus cooldown window and marks session attendance.
        """
        now = now_dt if now_dt is not None else get_ist_now()
        today = now.date()
        start_today = datetime.combine(today, datetime.min.time())
        end_today = datetime.combine(today, datetime.max.time())

        snapshot_rel_path = None
        if frame_bgr is not None:
            snapshot_rel_path = self._save_snapshot(student_id, frame_bgr, face_box)

        with get_db_context() as db:
            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            tenant_type = (tenant.tenant_type if tenant and tenant.tenant_type else "educational").lower()
            is_corporate = tenant_type in ["corporate", "company", "enterprise"]

            branding = db.query(SystemBranding).filter(SystemBranding.tenant_id == tenant_id).first()
            min_checkout_interval = branding.min_checkout_interval_minutes if branding and branding.min_checkout_interval_minutes is not None else 15
            if custom_cooldown_seconds is not None:
                min_checkout_interval = max(0, custom_cooldown_seconds // 60)

            student = db.query(Student).filter(Student.id == student_id, Student.tenant_id == tenant_id).first()
            if not student:
                return None
            if not student.is_active or (student.employment_status and student.employment_status.upper() in ["RELIEVED", "TERMINATED", "RESIGNED"]):
                logger.warning(f"Blocked attendance for relieved/inactive employee '{student.name}' (ID {student.id}).")
                return {
                    "attendance_logged": False,
                    "cooldown_active": False,
                    "is_relieved": True,
                    "status": "BLOCKED",
                    "shift_status": "BLOCKED",
                    "punch_type": "BLOCKED",
                    "message": f"Attendance Blocked: Employee '{student.name}' is Relieved / Inactive.",
                    "student_name": student.name,
                    "roll_number": student.roll_number,
                }

            # Resolve Employee Assigned Shift
            emp_shift = student.shift
            if not emp_shift and student.shift_id:
                emp_shift = db.query(WorkShift).filter(WorkShift.tenant_id == tenant_id, WorkShift.id == student.shift_id).first()
            if not emp_shift:
                emp_shift = db.query(WorkShift).filter(WorkShift.tenant_id == tenant_id, WorkShift.is_default == True).first()
            if not emp_shift:
                emp_shift = db.query(WorkShift).filter(WorkShift.tenant_id == tenant_id).first()

            if emp_shift:
                shift_in_str = emp_shift.start_time or "10:30"
                shift_out_str = emp_shift.end_time or "18:00"
                grace_mins = emp_shift.grace_period_minutes if emp_shift.grace_period_minutes is not None else 15
                is_night_shift = emp_shift.is_night_shift
            else:
                shift_in_str = branding.shift_check_in_time if branding and branding.shift_check_in_time else "10:30"
                shift_out_str = branding.shift_check_out_time if branding and branding.shift_check_out_time else "18:00"
                grace_mins = branding.shift_grace_minutes if branding and branding.shift_grace_minutes is not None else 15
                try:
                    sh, sm = map(int, shift_in_str.split(":"))
                    eh, em = map(int, shift_out_str.split(":"))
                    is_night_shift = (eh * 60 + em) < (sh * 60 + sm)
                except Exception:
                    is_night_shift = False

            if is_corporate:
                # ----------------------------------------------------
                # CORPORATE MULTI-PUNCH (CHECK-IN & CHECK-OUT) WORKFLOW
                # ----------------------------------------------------
                lookback_start = now - timedelta(hours=20) if is_night_shift else start_today
                existing_record = (
                    db.query(AttendanceRecord)
                    .filter(
                        AttendanceRecord.tenant_id == tenant_id,
                        AttendanceRecord.student_id == student_id,
                        AttendanceRecord.timestamp >= lookback_start,
                    )
                    .order_by(AttendanceRecord.timestamp.desc())
                    .first()
                )

                min_interval_secs = min_checkout_interval * 60
                if custom_cooldown_seconds is not None and custom_cooldown_seconds == 0:
                    min_interval_secs = 0

                if existing_record is None or existing_record.check_out_time is not None:
                    # EMPLOYEE IS CHECKING IN (FIRST SCAN OR SUBSEQUENT RE-ENTRY SESSION)
                    if existing_record is not None and existing_record.check_out_time is not None:
                        # Cooldown check since last checkout
                        elapsed_since_out = (now - existing_record.check_out_time).total_seconds()
                        if min_interval_secs > 0 and elapsed_since_out < min_interval_secs:
                            remaining_secs = max(1, int(min_interval_secs - elapsed_since_out))
                            return {
                                "attendance_logged": False,
                                "punch_type": "CHECK_OUT",
                                "cooldown_active": True,
                                "cooldown_remaining_seconds": remaining_secs,
                                "cooldown_remaining_minutes": round(remaining_secs / 60, 1),
                                "cooldown_window_minutes": min_checkout_interval,
                                "message": f"Check-Out already logged at {existing_record.check_out_time.strftime('%I:%M %p')}. Next Check-In enabled in {max(1, remaining_secs // 60)} min(s).",
                            }

                    # Evaluate shift on-time vs late check-in
                    if existing_record is None:
                        try:
                            in_parts = shift_in_str.split(":")
                            in_h, in_m = int(in_parts[0]), int(in_parts[1])
                            target_in = datetime.combine(today, datetime.min.time()).replace(hour=in_h, minute=in_m)
                            late_threshold = target_in + timedelta(minutes=grace_mins)
                            shift_status = "LATE_CHECKIN" if now > late_threshold else "ON_TIME"
                        except Exception:
                            shift_status = "ON_TIME"
                    else:
                        shift_status = "ON_TIME"

                    record = AttendanceRecord(
                        tenant_id=tenant_id,
                        student_id=student_id,
                        node_id=node_id,
                        timestamp=now,
                        confidence_distance=confidence_distance,
                        status="PRESENT",
                        snapshot_path=snapshot_rel_path,
                        geo_latitude=geo_latitude,
                        geo_longitude=geo_longitude,
                        geo_distance_meters=geo_distance_meters,
                        is_self_attendance=is_self_attendance,
                        punch_type="CHECK_IN",
                        check_in_time=now,
                        check_out_time=None,
                        work_duration_minutes=None,
                        shift_status=shift_status,
                    )
                    db.add(record)
                    db.flush()
                    self._update_node_stats(db, tenant_id, node_id)
                    db.commit()

                    self._last_logged_cache[(tenant_id, student_id)] = time.time()
                    log_data = record.to_dict()

                    self._broadcast_attendance(tenant_id, log_data)
                    logger.info(
                        f"[+] Corporate Check-In logged: Employee #{student_id} ('{student.name if student else 'N/A'}') "
                        f"at Node '{node_id}' [Tenant #{tenant_id}, Status={shift_status}, Dist={confidence_distance:.3f}]."
                    )
                    return {
                        "attendance_logged": True,
                        "punch_type": "CHECK_IN",
                        "shift_status": shift_status,
                        "work_duration_minutes": None,
                        "work_duration_formatted": "--",
                        "check_in_short": now.strftime("%I:%M %p"),
                        "check_out_short": "--",
                        "record": log_data,
                        "log_data": log_data,
                        "cooldown_active": False,
                        "cooldown_remaining_seconds": 0,
                        "message": f"Check-In registered at {now.strftime('%I:%M %p')}.",
                    }

                else:
                    # EMPLOYEE IS CHECKING OUT (CLOSING CURRENT ACTIVE SESSION)
                    ref_time = existing_record.check_in_time or existing_record.timestamp
                    elapsed_secs = (now - ref_time).total_seconds()

                    if min_interval_secs > 0 and elapsed_secs < min_interval_secs:
                        # Too soon after check-in -> suppress double punch
                        remaining_secs = max(1, int(min_interval_secs - elapsed_secs))
                        return {
                            "attendance_logged": False,
                            "punch_type": "CHECK_IN",
                            "cooldown_active": True,
                            "cooldown_remaining_seconds": remaining_secs,
                            "cooldown_remaining_minutes": round(remaining_secs / 60, 1),
                            "cooldown_window_minutes": min_checkout_interval,
                            "message": f"Check-In already logged at {ref_time.strftime('%I:%M %p')}. Checkout enabled in {max(1, remaining_secs // 60)} min(s).",
                        }

                    # Valid Check-Out Punch
                    existing_record.check_out_time = now
                    existing_record.punch_type = "CHECK_OUT"
                    if snapshot_rel_path:
                        existing_record.snapshot_path = snapshot_rel_path
                    existing_record.confidence_distance = confidence_distance
                    existing_record.node_id = node_id

                    duration_mins = max(0, int((now - ref_time).total_seconds() / 60))
                    existing_record.work_duration_minutes = duration_mins

                    # Evaluate early departure vs regular completion
                    try:
                        out_parts = shift_out_str.split(":")
                        out_h, out_m = int(out_parts[0]), int(out_parts[1])
                        check_in_dt = existing_record.check_in_time or existing_record.timestamp
                        target_out_date = check_in_dt.date() + timedelta(days=1) if is_night_shift else check_in_dt.date()
                        target_out = datetime.combine(target_out_date, datetime.min.time()).replace(hour=out_h, minute=out_m)
                        early_threshold = target_out - timedelta(minutes=grace_mins)
                        if now < early_threshold:
                            existing_record.shift_status = "EARLY_DEPARTURE"
                        else:
                            existing_record.shift_status = "COMPLETED"
                    except Exception:
                        existing_record.shift_status = "COMPLETED"

                    self._update_node_stats(db, tenant_id, node_id)
                    db.commit()

                    self._last_logged_cache[(tenant_id, student_id)] = time.time()
                    log_data = existing_record.to_dict()

                    hrs = duration_mins // 60
                    rem_mins = duration_mins % 60
                    dur_fmt = f"{hrs}h {rem_mins:02d}m" if hrs > 0 else f"{rem_mins}m"

                    self._broadcast_attendance(tenant_id, log_data)
                    logger.info(
                        f"[+] Corporate Check-Out logged: Employee #{student_id} ('{student.name if student else 'N/A'}') "
                        f"at Node '{node_id}' [Tenant #{tenant_id}, Duration={duration_mins} mins, Status={existing_record.shift_status}]."
                    )
                    return {
                        "attendance_logged": True,
                        "punch_type": "CHECK_OUT",
                        "shift_status": existing_record.shift_status,
                        "work_duration_minutes": duration_mins,
                        "work_duration_formatted": dur_fmt,
                        "check_in_short": ref_time.strftime("%I:%M %p"),
                        "check_out_short": now.strftime("%I:%M %p"),
                        "record": log_data,
                        "log_data": log_data,
                        "cooldown_active": False,
                        "cooldown_remaining_seconds": 0,
                        "message": f"Check-Out registered at {now.strftime('%I:%M %p')}. Session: {dur_fmt}.",
                    }

            else:
                # ----------------------------------------------------
                # EDUCATIONAL SINGLE-PUNCH ATTENDANCE WORKFLOW
                # ----------------------------------------------------
                can_log, remaining_secs, active_cd = self.should_log_attendance(
                    student_id=student_id,
                    node_id=node_id,
                    tenant_id=tenant_id,
                    custom_cooldown_seconds=custom_cooldown_seconds,
                )

                if not can_log:
                    return {
                        "attendance_logged": False,
                        "cooldown_active": True,
                        "cooldown_remaining_seconds": remaining_secs,
                        "cooldown_remaining_minutes": round(remaining_secs / 60, 1),
                        "cooldown_window_minutes": round(active_cd / 60, 1),
                    }

                self._last_logged_cache[(tenant_id, student_id)] = time.time()

                record = AttendanceRecord(
                    tenant_id=tenant_id,
                    student_id=student_id,
                    node_id=node_id,
                    timestamp=now,
                    confidence_distance=confidence_distance,
                    status="PRESENT",
                    snapshot_path=snapshot_rel_path,
                    geo_latitude=geo_latitude,
                    geo_longitude=geo_longitude,
                    geo_distance_meters=geo_distance_meters,
                    is_self_attendance=is_self_attendance,
                    punch_type="ATTENDANCE",
                    check_in_time=now,
                    check_out_time=None,
                    work_duration_minutes=None,
                    shift_status="PRESENT",
                )
                db.add(record)
                db.flush()
                self._update_node_stats(db, tenant_id, node_id)
                db.commit()

                log_data = record.to_dict()
                self._broadcast_attendance(tenant_id, log_data)

                logger.info(
                    f"[+] Attendance logged: Student #{student_id} ('{student.name if student else 'N/A'}') "
                    f"at Node '{node_id}' [Tenant #{tenant_id}, Dist={confidence_distance:.3f}]."
                )
                return {
                    "attendance_logged": True,
                    "record": log_data,
                    "log_data": log_data,
                    "cooldown_active": False,
                    "cooldown_remaining_seconds": 0,
                    "cooldown_window_minutes": round(active_cd / 60, 1),
                }

    def record_spoof_event(
        self,
        node_id: str,
        student_name: Optional[str] = None,
        reasons: Optional[List[str]] = None,
        tenant_id: int = DEFAULT_TENANT_ID,
    ):
        """Broadcasts real-time spoof attack security alert to subscribers."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.broadcast_event({
                    "type": "SPOOF_ATTEMPT",
                    "tenant_id": tenant_id,
                    "data": {
                        "tenant_id": tenant_id,
                        "node_id": node_id,
                        "student_name": student_name or "Unknown / Unverified",
                        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                        "reasons": reasons or ["Printed photo or digital screen attack detected."],
                    },
                }))
        except Exception:
            pass

    def record_node_heartbeat(
        self,
        node_id: str,
        location: str = "Classroom",
        fps: float = 2.0,
        tenant_id: int = DEFAULT_TENANT_ID,
    ):
        """Updates or registers a node heartbeat for a specific tenant in the database."""
        with get_db_context() as db:
            node = db.query(NodeDevice).filter(
                NodeDevice.tenant_id == tenant_id,
                NodeDevice.node_id == node_id
            ).first()

            if node:
                node.location = location
                node.last_heartbeat = get_ist_now()
                node.is_online = True
                node.fps = fps
            else:
                new_node = NodeDevice(
                    tenant_id=tenant_id,
                    node_id=node_id,
                    name=f"Node {node_id}",
                    location=location,
                    last_heartbeat=get_ist_now(),
                    is_online=True,
                    fps=fps,
                    total_detections=0,
                )
                db.add(new_node)

    def _save_snapshot(
        self,
        student_id: int,
        frame_bgr: np.ndarray,
        face_box: Optional[Dict[str, int]] = None,
    ) -> str:
        """Saves a labeled snapshot frame with an overlay bounding box for verification audit."""
        annotated = frame_bgr.copy()
        if face_box:
            top, right, bottom, left = face_box["top"], face_box["right"], face_box["bottom"], face_box["left"]
            cv2.rectangle(annotated, (left, top), (right, bottom), (0, 255, 0), 2)

        timestamp_str = get_ist_now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"attend_std{student_id}_{timestamp_str}.jpg"
        target_path = SNAPSHOTS_DIR / filename

        cv2.imwrite(str(target_path), annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return f"snapshots/{filename}"


# Global AttendanceManager instance
attendance_manager = AttendanceManager()
