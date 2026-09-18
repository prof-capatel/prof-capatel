import os
from pathlib import Path
from dotenv import load_dotenv

# Base Paths
BASE_DIR = Path(os.getenv("ATTENDANCE_BASE_DIR", str(Path(__file__).resolve().parent.parent)))
load_dotenv(BASE_DIR / ".env")
DATABASE_DIR = BASE_DIR / "database"
DATA_DIR = BASE_DIR / "data"
FACES_DIR = DATA_DIR / "faces"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
EXPORTS_DIR = DATA_DIR / "exports"
BRANDING_DIR = DATA_DIR / "branding"

# Ensure all persistent directories exist
for directory in [DATABASE_DIR, DATA_DIR, FACES_DIR, SNAPSHOTS_DIR, EXPORTS_DIR, BRANDING_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

from urllib.parse import quote_plus

# Database Configuration (MySQL SaaS Architecture)
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DB = os.getenv("MYSQL_DB", "face_system")

# SQLAlchemy Connection String pointing to local MySQL on port 3306
_ENCODED_USER = quote_plus(MYSQL_USER)
_ENCODED_PASSWORD = quote_plus(MYSQL_PASSWORD)
DATABASE_URL = f"mysql+pymysql://{_ENCODED_USER}:{_ENCODED_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"
# SQLite database path preserved for rollback and migration imports
SQLITE_DB_PATH = DATABASE_DIR / "attendance.db"
DEFAULT_TENANT_ID = 1
DEFAULT_TENANT_SLUG = "default"

# Face Recognition Settings (CPU-Tuned for High Accuracy & Low Latency)
FACE_DISTANCE_THRESHOLD = 0.55   # Calibrated Euclidean distance threshold (0.55 ensures high accuracy across lighting)
DETECTION_MODEL = "hog"          # HOG for fast and accurate CPU processing
DETECTION_SCALE = 0.5            # 0.5x downscaling for lightning-fast HOG detection
ENROLLMENT_SAMPLES_REQUIRED = 3  # Multi-angle enrollment: Front, Slight Left, Slight Right
UNKNOWN_FACE_LABEL = "Unknown"

# Attendance Logic
DEDUPLICATION_WINDOW_SECONDS = 300  # 5 minutes cooldown between repeated logs per student

# Server Network Settings
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8000

# Anti-Spoofing & Liveness Detection Settings
ENABLE_ANTI_SPOOFING = True
LIVENESS_THRESHOLD = 0.65            # Composite score threshold for texture, chromatic, and depth gradients
LIVENESS_CONFIRMATION_FRAMES = 5     # Consecutive sequence frames required before marking attendance

# Edge Node Defaults
DEFAULT_NODE_ID = "NODE-CLASSROOM-101"
DEFAULT_NODE_LOCATION = "Room 101 - Main Entrance"
DEFAULT_NODE_FPS = 2
