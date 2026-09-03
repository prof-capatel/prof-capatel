import logging
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import cv2

try:
    import face_recognition
except ImportError:
    face_recognition = None

from src.config import (
    FACE_DISTANCE_THRESHOLD,
    DETECTION_MODEL,
    DETECTION_SCALE,
    UNKNOWN_FACE_LABEL,
    ENABLE_ANTI_SPOOFING,
    DEFAULT_TENANT_ID,
)
from src.core.liveness_detector import liveness_detector, temporal_tracker
from src.database.models import Student, FaceEncoding, Tenant
from src.database.session import SessionLocal

logger = logging.getLogger("face_engine")
logger.setLevel(logging.INFO)


class FaceEngine:
    """
    Central Face Recognition & Vector Matching Engine with Multi-Tenant Partitioning.
    Optimized for CPU execution with downscaled HOG detection and
    vectorized in-memory Euclidean distance caching partitioned per tenant.
    """

    def __init__(self, distance_threshold: float = FACE_DISTANCE_THRESHOLD):
        self.distance_threshold = distance_threshold
        # In-memory cached matrix partitioned by tenant_id: tenant_id -> np.ndarray of shape (N, 128)
        self._tenant_vectors: Dict[int, np.ndarray] = {}
        # In-memory metadata list partitioned by tenant_id: tenant_id -> List[Dict]
        self._tenant_metadata: Dict[int, List[Dict[str, Any]]] = {}
        self._is_initialized = False

    def initialize(self, db_session=None, tenant_id: Optional[int] = None):
        """Preloads registered student face encodings into RAM partitioned by tenant."""
        if db_session is None:
            db = SessionLocal()
            try:
                self._load_cache_from_db(db, tenant_id=tenant_id)
            finally:
                db.close()
        else:
            self._load_cache_from_db(db_session, tenant_id=tenant_id)
        self._is_initialized = True
        total_samples = sum(len(meta) for meta in self._tenant_metadata.values())
        logger.info(
            f"FaceEngine loaded {total_samples} face vectors across {len(self._tenant_vectors)} tenant(s)."
        )

    def _load_cache_from_db(self, db, tenant_id: Optional[int] = None):
        """Loads active student face vectors from MySQL into memory matrices per tenant."""
        if tenant_id is not None:
            tenants = db.query(Tenant).filter(Tenant.id == tenant_id, Tenant.is_active == True).all()
        else:
            tenants = db.query(Tenant).filter(Tenant.is_active == True).all()

        for t in tenants:
            encodings = (
                db.query(FaceEncoding)
                .join(Student, FaceEncoding.student_id == Student.id)
                .filter(FaceEncoding.tenant_id == t.id, Student.is_active == True)
                .all()
            )

            vectors = []
            metadata = []

            for enc in encodings:
                try:
                    vec = enc.get_numpy_vector()
                    if vec.shape == (128,):
                        vectors.append(vec)
                        metadata.append({
                            "tenant_id": t.id,
                            "student_id": enc.student_id,
                            "name": enc.student.name,
                            "roll_number": enc.student.roll_number,
                            "department": enc.student.department,
                            "user_role": enc.student.user_role,
                            "sample_angle": enc.sample_angle,
                        })
                except Exception as e:
                    logger.error(f"Error loading vector for student {enc.student_id} (Tenant {t.id}): {e}")

            if vectors:
                self._tenant_vectors[t.id] = np.array(vectors, dtype=np.float64)
                self._tenant_metadata[t.id] = metadata
            else:
                self._tenant_vectors[t.id] = np.empty((0, 128), dtype=np.float64)
                self._tenant_metadata[t.id] = []

    def reload_cache(self, db=None, tenant_id: Optional[int] = None):
        """Hot-reloads cache after a new student is enrolled or updated."""
        self.initialize(db, tenant_id=tenant_id)

    def detect_and_recognize_faces(
        self,
        frame_bgr: np.ndarray,
        node_id: str = "DEFAULT",
        detection_scale: float = DETECTION_SCALE,
        tenant_id: int = DEFAULT_TENANT_ID,
        custom_temporal_frames: Optional[int] = None,
        is_single_shot: bool = False,
        enable_anti_spoofing: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """
        Takes a BGR image frame, detects all faces (using CPU-optimized scaled HOG),
        extracts 128-d vectors, matches against the tenant's in-memory vector cache,
        and runs anti-spoofing + temporal motion verification isolated per node & tenant.
        """
        if face_recognition is None:
            raise RuntimeError("face_recognition library is not loaded.")

        if frame_bgr is None or frame_bgr.size == 0:
            return []

        if not self._is_initialized or tenant_id not in self._tenant_vectors:
            self.initialize(tenant_id=tenant_id)

        rgb_frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

        # 1. Detect face bounding boxes (Multi-tier detection for high reliability)
        face_locations = []
        if DETECTION_SCALE < 1.0:
            small_rgb = cv2.resize(
                rgb_frame,
                (0, 0),
                fx=DETECTION_SCALE,
                fy=DETECTION_SCALE,
                interpolation=cv2.INTER_LINEAR,
            )
            small_locations = face_recognition.face_locations(small_rgb, model=DETECTION_MODEL)
            if small_locations:
                scale_factor = 1.0 / DETECTION_SCALE
                face_locations = [
                    (
                        int(top * scale_factor),
                        int(right * scale_factor),
                        int(bottom * scale_factor),
                        int(left * scale_factor),
                    )
                    for (top, right, bottom, left) in small_locations
                ]

        # Multi-Tier Fallback Tier 2: If downscaled image found 0 faces, retry at full 1.0x resolution
        if not face_locations:
            face_locations = face_recognition.face_locations(rgb_frame, model=DETECTION_MODEL)

        # Multi-Tier Fallback Tier 3: If still 0 faces on small/medium frames, try 1x upsample
        if not face_locations and min(rgb_frame.shape[:2]) <= 720:
            face_locations = face_recognition.face_locations(rgb_frame, number_of_times_to_upsample=1, model=DETECTION_MODEL)

        if not face_locations:
            return []

        # 2. Extract 128-d face encodings at original resolution
        detected_encodings = face_recognition.face_encodings(
            rgb_frame,
            known_face_locations=face_locations,
            num_jitters=1,  # 1 jitter for real-time CPU speed
        )

        # Determine effective anti-spoofing state
        is_anti_spoofing_active = enable_anti_spoofing if enable_anti_spoofing is not None else ENABLE_ANTI_SPOOFING

        results = []
        for location, encoding in zip(face_locations, detected_encodings):
            match_info = self.match_encoding(encoding, tenant_id=tenant_id)
            box = {
                "top": location[0],
                "right": location[1],
                "bottom": location[2],
                "left": location[3],
            }
            match_info["box"] = box

            # 3. Liveness & Anti-Spoofing Evaluation
            if is_anti_spoofing_active:
                liveness_res = liveness_detector.evaluate_liveness(frame_bgr, box)
                is_live = liveness_res["is_live"]
                liveness_score = liveness_res["score"]
                reasons = liveness_res["reasons"]

                # If single shot photo, temporal confirmation is immediate based on single frame
                if is_single_shot or custom_temporal_frames == 1:
                    is_temp_confirmed = is_live
                    frames_seen = 1
                    temp_status = "REAL" if is_live else "SPOOF_DETECTED"
                else:
                    # Temporal micro-motion tracking across consecutive stream frames isolated per node
                    student_id = match_info.get("student_id")
                    track_node_key = f"T{tenant_id}_{node_id}"
                    is_temp_confirmed, frames_seen, temp_status = temporal_tracker.update_track(
                        student_id=student_id,
                        face_box=box,
                        is_single_frame_live=is_live,
                        node_id=track_node_key,
                        custom_confirmation_frames=custom_temporal_frames,
                    )

                match_info["is_live"] = is_live
                match_info["liveness_score"] = liveness_score
                match_info["liveness_status"] = liveness_res["status"]
                match_info["temporal_confirmed"] = is_temp_confirmed
                match_info["temporal_status"] = temp_status
                match_info["temporal_frames"] = frames_seen
                match_info["liveness_reasons"] = reasons
            else:
                match_info["is_live"] = True
                match_info["liveness_score"] = 1.0
                match_info["liveness_status"] = "BYPASSED"
                match_info["temporal_confirmed"] = True
                match_info["temporal_status"] = "REAL"
                match_info["temporal_frames"] = 1
                match_info["liveness_reasons"] = ["Anti-spoofing disabled in institutional settings."]

            results.append(match_info)

        return results

    def match_encoding(self, target_encoding: np.ndarray, tenant_id: int = DEFAULT_TENANT_ID) -> Dict[str, Any]:
        """
        Vectorized Euclidean distance matching against tenant's cached student matrix.
        Returns the closest matching student if within distance_threshold.
        """
        cached_vectors = self._tenant_vectors.get(tenant_id)
        cached_metadata = self._tenant_metadata.get(tenant_id)

        if cached_vectors is None or len(cached_vectors) == 0:
            return {
                "tenant_id": tenant_id,
                "student_id": None,
                "name": UNKNOWN_FACE_LABEL,
                "roll_number": "N/A",
                "department": "N/A",
                "user_role": "student",
                "distance": 1.0,
                "confidence_pct": 0.0,
                "is_match": False,
            }

        # Vectorized Euclidean Distance: np.linalg.norm(A - B) along axis=1
        distances = np.linalg.norm(cached_vectors - target_encoding, axis=1)
        best_idx = int(np.argmin(distances))
        min_dist = float(distances[best_idx])

        # Confidence percentage mapping (0.0 distance = 100%, 0.6 distance = 0%)
        confidence_pct = max(0.0, min(100.0, round((1.0 - (min_dist / 0.60)) * 100, 1)))

        if min_dist <= self.distance_threshold:
            matched_meta = cached_metadata[best_idx]
            return {
                "tenant_id": tenant_id,
                "student_id": matched_meta["student_id"],
                "name": matched_meta["name"],
                "roll_number": matched_meta["roll_number"],
                "department": matched_meta["department"],
                "user_role": matched_meta.get("user_role", "student"),
                "distance": round(min_dist, 4),
                "threshold": self.distance_threshold,
                "confidence_pct": confidence_pct,
                "is_match": True,
            }
        else:
            closest_meta = cached_metadata[best_idx] if cached_metadata else None
            return {
                "tenant_id": tenant_id,
                "student_id": None,
                "name": UNKNOWN_FACE_LABEL,
                "roll_number": "N/A",
                "department": "N/A",
                "user_role": "student",
                "closest_candidate_name": closest_meta["name"] if closest_meta else None,
                "closest_candidate_roll": closest_meta["roll_number"] if closest_meta else None,
                "distance": round(min_dist, 4),
                "threshold": self.distance_threshold,
                "confidence_pct": 0.0,
                "is_match": False,
            }

    @staticmethod
    def compute_single_face_vector(image_bgr: np.ndarray) -> Tuple[Optional[np.ndarray], Optional[Tuple[int, int, int, int]], str]:
        """
        Used during student enrollment.
        Ensures exactly one clear face is present and extracts its 128-d vector.
        """
        if face_recognition is None:
            return None, None, "face_recognition library is not installed."

        rgb_image = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        locations = face_recognition.face_locations(rgb_image, model=DETECTION_MODEL)

        # Multi-tier fallback with upsample for small/cropped images
        if len(locations) == 0:
            locations = face_recognition.face_locations(rgb_image, number_of_times_to_upsample=1, model=DETECTION_MODEL)
        if len(locations) == 0:
            locations = face_recognition.face_locations(rgb_image, number_of_times_to_upsample=2, model=DETECTION_MODEL)

        if len(locations) == 0:
            return None, None, "No face detected in frame. Please look directly at the camera."
        if len(locations) > 1:
            return None, None, "Multiple faces detected. Please ensure only one person is in frame."

        encodings = face_recognition.face_encodings(rgb_image, known_face_locations=locations, num_jitters=2)
        if not encodings:
            return None, None, "Could not extract facial features. Check lighting."

        return encodings[0], locations[0], "Success"


# Singleton instance for the central server
face_engine = FaceEngine()
