import base64
from typing import Optional, Tuple
import cv2
import numpy as np


def decode_image_bytes(image_bytes: bytes) -> Optional[np.ndarray]:
    """Decodes raw JPEG/PNG image bytes into an OpenCV BGR numpy array."""
    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return frame
    except Exception:
        return None


def encode_frame_to_jpeg(frame_bgr: np.ndarray, quality: int = 80) -> bytes:
    """Encodes an OpenCV BGR image into JPEG bytes with configurable compression quality."""
    success, buffer = cv2.imencode(".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not success:
        raise ValueError("Failed to encode frame to JPEG.")
    return buffer.tobytes()


def encode_frame_to_base64(frame_bgr: np.ndarray, quality: int = 80) -> str:
    """Encodes an OpenCV BGR frame into a Base64 data URL string."""
    jpeg_bytes = encode_frame_to_jpeg(frame_bgr, quality=quality)
    b64_str = base64.b64encode(jpeg_bytes).decode("utf-8")
    return f"data:image/jpeg;base64,{b64_str}"


def resize_with_aspect_ratio(
    image: np.ndarray,
    max_width: int = 640,
    max_height: int = 480,
) -> np.ndarray:
    """Resizes an image maintaining original aspect ratio without distortion."""
    h, w = image.shape[:2]
    scale = min(max_width / w, max_height / h)
    if scale >= 1.0:
        return image
    new_w = int(w * scale)
    new_h = int(h * scale)
    return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)


def evaluate_image_quality(frame_bgr: np.ndarray) -> Tuple[bool, str]:
    """
    Validates image brightness and blurriness for face recognition enrollment.
    """
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    
    # 1. Check brightness
    mean_brightness = np.mean(gray)
    if mean_brightness < 40:
        return False, "Frame is too dark. Increase ambient lighting."
    if mean_brightness > 225:
        return False, "Frame is overexposed / too bright."

    # 2. Check blurriness via Laplacian variance
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    if laplacian_var < 50.0:
        return False, "Frame is blurry. Please hold steady."

    return True, "Good quality"
