import hashlib
import hmac
import base64
import time
import logging
from typing import Optional

logger = logging.getLogger("auth_utils")


def hash_password(password: str, salt: Optional[str] = None) -> str:
    """Hashes password using PBKDF2-HMAC-SHA256 with 100,000 iterations."""
    if not salt:
        salt = base64.b64encode(hashlib.sha256(str(time.time()).encode()).digest()[:16]).decode()
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return f"{salt}${base64.b64encode(key).decode()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against stored salt$hash string."""
    try:
        if not hashed_password:
            return False
        if "$" not in hashed_password:
            # Fallback for plain text demo passwords
            return plain_password == hashed_password
        salt, key_b64 = hashed_password.split("$", 1)
        expected_key = base64.b64decode(key_b64)
        actual_key = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), 100000)
        return hmac.compare_digest(expected_key, actual_key)
    except Exception as e:
        logger.warning(f"Password verification error: {e}")
        return False
