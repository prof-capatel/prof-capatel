import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(r"D:\Attendance System")
DATABASE_DIR = BASE_DIR / "database"
DATA_DIR = BASE_DIR / "data"
FACES_DIR = DATA_DIR / "faces"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
EXPORTS_DIR = DATA_DIR / "exports"
BRANDING_DIR = DATA_DIR / "branding"

# Ensure all persistent directories exist
for directory in [DATABASE_DIR, DATA_DIR, FACES_DIR, SNAPSHOTS_DIR, EXPORTS_DIR, BRANDING_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Database Configuration
DATABASE_URL = f"sqlite:///{DATABASE_DIR / 'attendance.db'}"

# Face Recognition Settings (CPU-Tuned for High Accuracy & Low Latency)
FACE_DISTANCE_THRESHOLD = 0.52   # Stricter than default 0.60 for minimal false positives
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
