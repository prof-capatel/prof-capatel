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
)
from src.core.liveness_detector import liveness_detector, temporal_tracker
from src.database.models import Student, FaceEncoding
from src.database.session import SessionLocal

logger = logging.getLogger("face_engine")
logger.setLevel(logging.INFO)


class FaceEngine:
    """
    Central Face Recognition & Vector Matching Engine.
    Optimized for CPU execution with downscaled HOG detection and
    vectorized in-memory Euclidean distance caching.
    """

    def __init__(self, distance_threshold: float = FACE_DISTANCE_THRESHOLD):
        self.distance_threshold = distance_threshold
        # In-memory cached matrix for fast vector matching
        # Shape: (N, 128) where N is the total registered face sample vectors across all students
        self._cached_vectors: Optional[np.ndarray] = None
        self._cached_metadata: List[Dict[str, Any]] = []
        self._is_initialized = False

    def initialize(self, db_session=None):
        """Preloads all registered student face encodings into RAM."""
        if db_session is None:
            db = SessionLocal()
            try:
                self._load_cache_from_db(db)
            finally:
                db.close()
        else:
            self._load_cache_from_db(db_session)
        self._is_initialized = True
        logger.info(f"FaceEngine loaded {len(self._cached_metadata)} face vector samples into memory.")

    def _load_cache_from_db(self, db):
        """Loads all active student face vectors from SQLite into memory matrix."""
        encodings = (
            db.query(FaceEncoding)
            .join(Student)
            .filter(Student.is_active == True)
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
                        "student_id": enc.student_id,
                        "name": enc.student.name,
                        "roll_number": enc.student.roll_number,
                        "department": enc.student.department,
                        "sample_angle": enc.sample_angle,
                    })
            except Exception as e:
                logger.error(f"Error loading vector for student {enc.student_id}: {e}")

        if vectors:
            self._cached_vectors = np.array(vectors, dtype=np.float64)
            self._cached_metadata = metadata
        else:
            self._cached_vectors = np.empty((0, 128), dtype=np.float64)
            self._cached_metadata = []

    def reload_cache(self, db=None):
        """Hot-reloads cache after a new student is enrolled."""
        self.initialize(db)

    def detect_and_recognize_faces(
        self,
        frame_bgr: np.ndarray,
        detection_scale: float = DETECTION_SCALE,
    ) -> List[Dict[str, Any]]:
        """
        Takes a BGR image frame, detects all faces (using CPU-optimized scaled HOG),
        extracts 128-d vectors, and matches against the in-memory vector cache.
        """
        if face_recognition is None:
            raise RuntimeError("face_recognition library is not loaded.")

        if not self._is_initialized:
            self.initialize()

        # Convert BGR to RGB (dlib/face_recognition uses RGB)
        rgb_frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        height, width = rgb_frame.shape[:2]

        # 1. CPU Acceleration: Downscale frame for fast HOG detection
        if detection_scale < 1.0:
            small_rgb = cv2.resize(rgb_frame, (0, 0), fx=detection_scale, fy=detection_scale)
            # Detect face bounding boxes on smaller frame
            small_locations = face_recognition.face_locations(small_rgb, model=DETECTION_MODEL)
            # Scale bounding box coordinates back to full resolution
            scale_factor = 1.0 / detection_scale
            face_locations = [
                (
                    int(top * scale_factor),
                    int(right * scale_factor),
                    int(bottom * scale_factor),
                    int(left * scale_factor),
                )
                for (top, right, bottom, left) in small_locations
            ]
        else:
            face_locations = face_recognition.face_locations(rgb_frame, model=DETECTION_MODEL)

        if not face_locations:
            return []

        # 2. Extract 128-d face encodings at original resolution
        detected_encodings = face_recognition.face_encodings(
            rgb_frame,
            known_face_locations=face_locations,
            num_jitters=1,  # 1 jitter for real-time CPU speed
        )

        results = []
        for location, encoding in zip(face_locations, detected_encodings):
            match_info = self.match_encoding(encoding)
            box = {
                "top": location[0],
                "right": location[1],
                "bottom": location[2],
                "left": location[3],
            }
            match_info["box"] = box

            # 3. Liveness & Anti-Spoofing Evaluation
            if ENABLE_ANTI_SPOOFING:
                liveness_res = liveness_detector.evaluate_liveness(frame_bgr, box)
                is_live = liveness_res["is_live"]
                liveness_score = liveness_res["score"]
                reasons = liveness_res["reasons"]

                # Temporal micro-motion tracking across consecutive frames
                student_id = match_info.get("student_id")
                is_temp_confirmed, frames_seen, temp_status = temporal_tracker.update_track(
                    student_id=student_id,
                    face_box=box,
                    is_single_frame_live=is_live,
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
                match_info["liveness_status"] = "REAL"
                match_info["temporal_confirmed"] = True
                match_info["temporal_status"] = "REAL"
                match_info["temporal_frames"] = 3
                match_info["liveness_reasons"] = ["Anti-spoofing disabled."]

            results.append(match_info)

        return results

    def match_encoding(self, target_encoding: np.ndarray) -> Dict[str, Any]:
        """
        Vectorized Euclidean distance matching against cached student matrix.
        Returns the closest matching student if within distance_threshold.
        """
        if self._cached_vectors is None or len(self._cached_vectors) == 0:
            return {
                "student_id": None,
                "name": UNKNOWN_FACE_LABEL,
                "roll_number": "N/A",
                "department": "N/A",
                "distance": 1.0,
                "confidence_pct": 0.0,
                "is_match": False,
            }

        # Vectorized Euclidean Distance: np.linalg.norm(A - B) along axis=1
        distances = np.linalg.norm(self._cached_vectors - target_encoding, axis=1)
        best_idx = int(np.argmin(distances))
        min_dist = float(distances[best_idx])

        # Confidence percentage mapping (0.0 distance = 100%, 0.6 distance = 0%)
        confidence_pct = max(0.0, min(100.0, round((1.0 - (min_dist / 0.60)) * 100, 1)))

        if min_dist <= self.distance_threshold:
            matched_meta = self._cached_metadata[best_idx]
            return {
                "student_id": matched_meta["student_id"],
                "name": matched_meta["name"],
                "roll_number": matched_meta["roll_number"],
                "department": matched_meta["department"],
                "distance": round(min_dist, 4),
                "confidence_pct": confidence_pct,
                "is_match": True,
            }
        else:
            return {
                "student_id": None,
                "name": UNKNOWN_FACE_LABEL,
                "roll_number": "N/A",
                "department": "N/A",
                "distance": round(min_dist, 4),
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
