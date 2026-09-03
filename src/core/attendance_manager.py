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
from src.database.models import AttendanceRecord, NodeDevice, Student, SystemBranding
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

    def mark_attendance(
        self,
        student_id: int,
        node_id: str,
        confidence_distance: float,
        frame_bgr: Optional[np.ndarray] = None,
        face_box: Optional[Dict[str, int]] = None,
        tenant_id: int = DEFAULT_TENANT_ID,
        custom_cooldown_seconds: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Processes a recognized face:
        - Evaluates institutional cooldown window.
        - If active: suppresses duplicate and returns cooldown status metadata.
        - If eligible: persists AttendanceRecord in MySQL, stores snapshot, updates node, and broadcasts SSE event.
        """
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

        current_time = time.time()
        self._last_logged_cache[(tenant_id, student_id)] = current_time

        snapshot_rel_path = None
        if frame_bgr is not None:
            snapshot_rel_path = self._save_snapshot(student_id, frame_bgr, face_box)

        # Database insertion
        with get_db_context() as db:
            record = AttendanceRecord(
                tenant_id=tenant_id,
                student_id=student_id,
                node_id=node_id,
                timestamp=get_ist_now(),
                confidence_distance=confidence_distance,
                status="PRESENT",
                snapshot_path=snapshot_rel_path,
            )
            db.add(record)
            db.flush()

            # Update NodeDevice statistics scoped to tenant
            node = db.query(NodeDevice).filter(
                NodeDevice.tenant_id == tenant_id,
                NodeDevice.node_id == node_id
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
                    location="Classroom",
                    last_heartbeat=get_ist_now(),
                    is_online=True,
                    total_detections=1,
                )
                db.add(new_node)

            db.commit()

            student = db.query(Student).filter(Student.id == student_id, Student.tenant_id == tenant_id).first()
            log_data = record.to_dict()

            # Trigger asynchronous broadcast if event loop is running
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

            # Also publish synchronously to background threads
            self.publish({
                "type": "ATTENDANCE_LOGGED",
                "tenant_id": tenant_id,
                "data": log_data,
            })

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
