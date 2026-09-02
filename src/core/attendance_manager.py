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
)
from src.database.models import AttendanceRecord, NodeDevice, Student
from src.database.session import SessionLocal, get_db_context

logger = logging.getLogger("attendance_manager")
logger.setLevel(logging.INFO)


class AttendanceManager:
    """
    Manages attendance deduplication window, database record persistence,
    snapshot storage, and real-time live event dispatching.
    """

    def __init__(self, cooldown_seconds: int = DEDUPLICATION_WINDOW_SECONDS):
        self.cooldown_seconds = cooldown_seconds
        # In-memory sliding window cache: (student_id, node_id) -> last_logged_timestamp (float)
        self._last_logged_cache: Dict[Tuple[int, str], float] = {}
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

    def should_log_attendance(self, student_id: int, node_id: str) -> bool:
        """
        Checks whether the student can be logged at this node based on
        the sliding deduplication window (5 mins).
        """
        key = (student_id, node_id)
        current_time = time.time()
        last_time = self._last_logged_cache.get(key)

        if last_time is None or (current_time - last_time) >= self.cooldown_seconds:
            return True
        return False

    def mark_attendance(
        self,
        student_id: int,
        node_id: str,
        confidence_distance: float,
        frame_bgr: Optional[np.ndarray] = None,
        face_box: Optional[Dict[str, int]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Processes a recognized face:
        - Evaluates deduplication cooldown.
        - Persists AttendanceRecord in SQLite.
        - Saves snapshot crop.
        - Updates node device stats.
        - Broadcasts live event.
        """
        if not self.should_log_attendance(student_id, node_id):
            return None  # Suppressed due to cooldown

        current_time = time.time()
        self._last_logged_cache[(student_id, node_id)] = current_time

        snapshot_rel_path = None
        if frame_bgr is not None:
            snapshot_rel_path = self._save_snapshot(student_id, frame_bgr, face_box)

        # Database insertion
        with get_db_context() as db:
            record = AttendanceRecord(
                student_id=student_id,
                node_id=node_id,
                timestamp=datetime.utcnow(),
                confidence_distance=confidence_distance,
                status="PRESENT",
                snapshot_path=snapshot_rel_path,
            )
            db.add(record)
            db.flush()

            # Update NodeDevice statistics
            node = db.query(NodeDevice).filter(NodeDevice.node_id == node_id).first()
            if node:
                node.last_heartbeat = datetime.utcnow()
                node.is_online = True
                node.total_detections += 1
            else:
                new_node = NodeDevice(
                    node_id=node_id,
                    name=f"Node {node_id}",
                    location="Classroom",
                    last_heartbeat=datetime.utcnow(),
                    is_online=True,
                    total_detections=1,
                )
                db.add(new_node)

            db.commit()

            student = db.query(Student).filter(Student.id == student_id).first()
            log_data = record.to_dict()

            # Trigger asynchronous broadcast if event loop is running
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.broadcast_event({
                        "type": "ATTENDANCE_LOGGED",
                        "data": log_data,
                    }))
            except Exception:
                pass

            return log_data

    def record_spoof_event(self, node_id: str, student_name: Optional[str] = None, reasons: Optional[List[str]] = None):
        """Broadcasts real-time spoof attack security alert to subscribers."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.broadcast_event({
                    "type": "SPOOF_ATTEMPT",
                    "data": {
                        "node_id": node_id,
                        "student_name": student_name or "Unknown / Unverified",
                        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                        "reasons": reasons or ["Printed photo or digital screen attack detected."],
                    },
                }))
        except Exception:
            pass

    def record_node_heartbeat(self, node_id: str, fps: float = 2.0, location: str = "Classroom"):
        """Records node health and heartbeat in database."""
        with get_db_context() as db:
            node = db.query(NodeDevice).filter(NodeDevice.node_id == node_id).first()
            if node:
                node.last_heartbeat = datetime.utcnow()
                node.is_online = True
                node.fps = fps
            else:
                new_node = NodeDevice(
                    node_id=node_id,
                    name=f"Node {node_id}",
                    location=location,
                    last_heartbeat=datetime.utcnow(),
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

        timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"attend_std{student_id}_{timestamp_str}.jpg"
        target_path = SNAPSHOTS_DIR / filename

        cv2.imwrite(str(target_path), annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return f"snapshots/{filename}"


# Global AttendanceManager instance
attendance_manager = AttendanceManager()
