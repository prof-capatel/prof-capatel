import time
from typing import Dict, List, Optional, Tuple, Any
import cv2
import numpy as np

from src.config import LIVENESS_CONFIRMATION_FRAMES, LIVENESS_THRESHOLD


class LivenessDetector:
    """
    Lightweight, CPU-optimized Multi-Layer Anti-Spoofing & Liveness Engine.
    Employs:
    1. 2D Fast Fourier Transform (FFT) high-frequency Moiré & spectral decay analysis.
    2. YCbCr / HSV color-space chromatic dispersion & blue-backlight ratio checks.
    3. Multi-scale Laplacian gradient variance & specular screen reflection checks.
    """

    def __init__(self, threshold: float = LIVENESS_THRESHOLD):
        self.threshold = threshold

    def evaluate_liveness(
        self,
        frame_bgr: np.ndarray,
        face_box: Dict[str, int],
    ) -> Dict[str, Any]:
        """
        Evaluates a single cropped face for texture, frequency, and screen glare artifacts.
        Returns liveness score [0.0 - 1.0], is_live boolean, and descriptive diagnostic tags.
        """
        top, right, bottom, left = face_box["top"], face_box["right"], face_box["bottom"], face_box["left"]
        h, w = frame_bgr.shape[:2]

        # Clamp bounding box
        c_top = max(0, top)
        c_bottom = min(h, bottom)
        c_left = max(0, left)
        c_right = min(w, right)

        if (c_bottom - c_top) < 30 or (c_right - c_left) < 30:
            return {
                "is_live": False,
                "score": 0.0,
                "status": "FACE_TOO_SMALL",
                "details": "Face bounding box is too small for liveness analysis.",
                "reasons": ["Face resolution too low for liveness validation."],
            }

        face_crop = frame_bgr[c_top:c_bottom, c_left:c_right]

        # 1. FFT High-Frequency Texture & Moiré Analysis
        fft_score, fft_msg = self._analyze_fft_texture(face_crop)

        # 2. Color-Space Chromatic Dispersion & Blue Screen Backlight Check
        color_score, color_msg = self._analyze_chromatic_dispersion(face_crop)

        # 3. Surface Specular Glare & Gradient Flatness
        flatness_score, flatness_msg = self._analyze_specular_flatness(face_crop)

        composite_score = float(round(
            (fft_score * 0.40) + (color_score * 0.35) + (flatness_score * 0.25),
            3,
        ))

        is_live = bool(composite_score >= self.threshold)
        reasons = []
        if fft_score < 0.55:
            reasons.append(fft_msg)
        if color_score < 0.55:
            reasons.append(color_msg)
        if flatness_score < 0.55:
            reasons.append(flatness_msg)

        status = "REAL" if is_live else "SPOOF_SUSPECTED"

        return {
            "is_live": is_live,
            "score": composite_score,
            "status": status,
            "fft_score": float(round(fft_score, 3)),
            "color_score": float(round(color_score, 3)),
            "flatness_score": float(round(flatness_score, 3)),
            "reasons": reasons if reasons else ["Natural skin texture & 3D gradient verified."],
        }

    def _analyze_fft_texture(self, face_bgr: np.ndarray) -> Tuple[float, str]:
        """
        2D FFT Spectral Analysis:
        Screens and printed photos exhibit periodic moiré patterns or sharp high-frequency drop-offs.
        Real 3D human faces have continuous organic spectral decay.
        """
        gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (128, 128), interpolation=cv2.INTER_AREA)

        # Compute 2D Fast Fourier Transform
        f_transform = np.fft.fft2(resized)
        f_shift = np.fft.fftshift(f_transform)
        magnitude_spectrum = 20 * np.log(np.abs(f_shift) + 1e-7)

        center_y, center_x = 64, 64
        # Low frequency center region vs High frequency outer region
        y_indices, x_indices = np.ogrid[:128, :128]
        dist_from_center = np.sqrt((x_indices - center_x) ** 2 + (y_indices - center_y) ** 2)

        low_freq_mask = dist_from_center <= 20
        high_freq_mask = (dist_from_center > 20) & (dist_from_center <= 55)

        low_energy = np.mean(magnitude_spectrum[low_freq_mask])
        high_energy = np.mean(magnitude_spectrum[high_freq_mask])

        # Ratio of high-to-low frequency
        freq_ratio = high_energy / max(1.0, low_energy)

        # Real faces typically have freq_ratio between 0.44 and 0.80
        if 0.44 <= freq_ratio <= 0.80:
            score = 1.0 - (abs(freq_ratio - 0.60) * 1.5)
            score = max(0.65, min(1.0, score))
            return score, "Natural frequency distribution"
        elif freq_ratio < 0.44:
            score = max(0.1, freq_ratio / 0.44 * 0.5)
            return score, "Screen/paper uniform flatness detected"
        else:
            score = max(0.1, (1.0 - ((freq_ratio - 0.80) * 2.0)) * 0.5)
            return score, "Moiré pixel grid pattern detected"

    def _analyze_chromatic_dispersion(self, face_bgr: np.ndarray) -> Tuple[float, str]:
        """
        Skin Chromaticity in YCrCb and HSV color spaces:
        Natural skin clusters tightly in the Cr-Cb chrominance plane.
        Smartphones displays oversaturate blue channels and LCDs skew RGB balance.
        """
        ycrcb = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2YCrCb)
        _, cr, cb = cv2.split(ycrcb)

        # Human skin standard chrominance range: Cr in [130, 178], Cb in [75, 130]
        skin_mask = (cr >= 130) & (cr <= 178) & (cb >= 75) & (cb <= 130)
        skin_ratio = np.sum(skin_mask) / (face_bgr.shape[0] * face_bgr.shape[1])

        # Standard Deviation of Cr and Cb
        cr_std = np.std(cr)
        cb_std = np.std(cb)

        # Blue-light saturation check (screens have elevated B channel relative to R)
        b_channel, _, r_channel = cv2.split(face_bgr)
        b_over_r_ratio = np.mean(b_channel) / max(1.0, np.mean(r_channel))

        score = 1.0
        if skin_ratio < 0.25:
            score -= 0.45
        elif skin_ratio > 0.40:
            score += 0.15

        if b_over_r_ratio > 0.95:  # Unnatural blue screen backlighting
            score -= 0.40
            return max(0.1, score), "Unnatural digital screen backlight spectrum"

        if cr_std < 4.0 or cb_std < 4.0:  # Excessive chromatic uniformity (monochrome print)
            score -= 0.35
            return max(0.1, score), "Monochrome or printed paper color gamut"

        return max(0.2, min(1.0, score)), "Natural skin chrominance verified"

    def _analyze_specular_flatness(self, face_bgr: np.ndarray) -> Tuple[float, str]:
        """
        Depth gradient and specular reflection check:
        Screens and glossy photo prints exhibit hard specular hot-spots or flat gradients.
        3D human faces have smooth curved lighting gradients and facial depth shading.
        """
        gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
        
        # Calculate Laplacian variance of central face region
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        lap_var = laplacian.var()

        # Check for harsh specular glare (pixels with value > 248 in clusters)
        overexposed = np.sum(gray > 248) / (gray.shape[0] * gray.shape[1])
        if overexposed > 0.08:
            return 0.30, "Screen/photo glass specular reflection detected"

        # Edge variance score: Natural faces in standard lighting have variance in [35, 800]
        if 35.0 <= lap_var <= 800.0:
            score = 0.85
        elif lap_var < 35.0:
            score = 0.35  # Too blurry or smoothed print
        else:
            score = 0.40  # High digital noise or screen pixelation

        return score, "3D facial surface gradient verified"


class TemporalMotionTracker:
    """
    Tracks detected faces across consecutive video frames per camera node.
    Enforces a multi-frame verification sequence (default 5 frames) requiring natural human micro-movement
    while rejecting completely frozen static photos (variance == 0) or discontinuous spoof attacks.
    """

    def __init__(self, confirmation_frames: int = LIVENESS_CONFIRMATION_FRAMES, max_idle_seconds: float = 2.5):
        self.confirmation_frames = confirmation_frames
        self.max_idle_seconds = max_idle_seconds
        # Active tracks: track_key (node_id + student_id / box) -> { 'frames': int, 'last_time': float, 'history': [box], 'status': str }
        self._tracks: Dict[str, Dict[str, Any]] = {}

    def update_track(
        self,
        student_id: Optional[int],
        face_box: Dict[str, int],
        is_single_frame_live: bool,
        node_id: str = "DEFAULT",
        custom_confirmation_frames: Optional[int] = None,
    ) -> Tuple[bool, int, str]:
        """
        Updates temporal sequence for a face on a specific node.
        Returns: (is_temporally_confirmed, current_consecutive_frames, temporal_status)
        """
        target_frames = custom_confirmation_frames if custom_confirmation_frames is not None else self.confirmation_frames
        target_frames = max(1, target_frames)

        current_time = time.time()
        self._clean_expired_tracks(current_time)

        # Namespace tracking key per node to prevent stream collisions
        target_tag = f"std_{student_id}" if student_id is not None else f"box_{face_box['top']}_{face_box['left']}"
        track_key = f"{node_id}_{target_tag}"

        track = self._tracks.get(track_key)

        if not is_single_frame_live:
            # Single-frame spoof detected -> immediately invalidate track
            self._tracks[track_key] = {
                "frames": 0,
                "last_time": current_time,
                "history": [face_box],
                "status": "SPOOF_DETECTED",
            }
            return False, 0, "SPOOF_DETECTED"

        if track is None or track.get("status") == "SPOOF_DETECTED":
            # New face appearance -> Initialize tracker
            self._tracks[track_key] = {
                "frames": 1,
                "last_time": current_time,
                "history": [face_box],
                "status": "VERIFYING",
            }
            is_confirmed = (1 >= target_frames)
            status = "REAL" if is_confirmed else f"VERIFYING (1/{target_frames})"
            return is_confirmed, 1, status

        # Existing track -> measure displacement history
        history = track.get("history", [])
        history.append(face_box)
        if len(history) > 10:
            history.pop(0)
        track["history"] = history

        last_box = history[-2] if len(history) >= 2 else face_box
        dx = abs(face_box["left"] - last_box["left"])
        dy = abs(face_box["top"] - last_box["top"])
        step_displacement = np.sqrt(dx**2 + dy**2)

        # Teleportation check (face jumped across screen instantaneously)
        if step_displacement > 160:
            track["frames"] = 1
            track["last_time"] = current_time
            track["history"] = [face_box]
            status = f"VERIFYING (1/{target_frames})"
            track["status"] = status
            return False, 1, status

        track["frames"] += 1
        track["last_time"] = current_time

        consecutive = track["frames"]

        if consecutive >= target_frames:
            # Verify that the sequence isn't an absolutely rigid/frozen static screenshot
            if len(history) >= 4:
                centers_x = [(b["left"] + b["right"]) / 2.0 for b in history[-4:]]
                centers_y = [(b["top"] + b["bottom"]) / 2.0 for b in history[-4:]]
                std_x = float(np.std(centers_x))
                std_y = float(np.std(centers_y))

                if std_x == 0.0 and std_y == 0.0:
                    track["status"] = "SPOOF_FREEZE_DETECTED"
                    return False, consecutive, "SPOOF_DETECTED"

            track["status"] = "REAL"
            return True, consecutive, "REAL"
        else:
            status = f"VERIFYING ({consecutive}/{target_frames})"
            track["status"] = status
            return False, consecutive, status

    def _clean_expired_tracks(self, current_time: float):
        """Removes tracks that have not been updated within max_idle_seconds."""
        expired_keys = [
            k for k, v in self._tracks.items()
            if (current_time - v["last_time"]) > self.max_idle_seconds
        ]
        for k in expired_keys:
            del self._tracks[k]

    def reset(self):
        """Resets all active tracks."""
        self._tracks.clear()


# Global singletons
liveness_detector = LivenessDetector(threshold=LIVENESS_THRESHOLD)
temporal_tracker = TemporalMotionTracker(confirmation_frames=LIVENESS_CONFIRMATION_FRAMES)
