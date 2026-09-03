import io
import logging
from typing import Optional
import cv2
import numpy as np
from PIL import Image, ImageOps

logger = logging.getLogger("image_utils")


def decode_image_with_exif(image_bytes: bytes) -> Optional[np.ndarray]:
    """
    Decodes raw image bytes (JPEG/PNG/WebP) into a standard OpenCV BGR numpy array
    with automatic EXIF orientation transposition.
    
    Why this is critical:
    Smartphones (iOS Safari, Android Chrome) capture vertical portrait photos with the
    raw CCD sensor in landscape, saving a 90-degree rotation in the EXIF orientation tag (Tag 6).
    Standard cv2.imdecode ignores EXIF orientation, resulting in sideways 90° images where
    HOG face detection returns 0 faces ("No face detected").
    
    This function automatically transposes the image to upright vertical orientation before decoding.
    """
    if not image_bytes or len(image_bytes) == 0:
        return None

    try:
        pil_img = Image.open(io.BytesIO(image_bytes))
        # Auto-rotate according to EXIF orientation tag
        pil_img = ImageOps.exif_transpose(pil_img)

        if pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")

        rgb_arr = np.array(pil_img)
        # Convert RGB to OpenCV BGR
        return cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2BGR)
    except Exception as e:
        logger.warning(f"PIL EXIF decoding failed ({e}), falling back to cv2.imdecode...")
        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            return cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        except Exception as e2:
            logger.error(f"cv2.imdecode fallback failed: {e2}")
            return None
