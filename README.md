# Thin-Client Face Recognition Attendance System

A modular, high-accuracy, local-first face recognition attendance system using a **Thin-Client / Central-Server Architecture**.

---

## 🏛️ Architecture Overview

```
[ Raspberry Pi Zero Nodes (Simulated) ] ── (HTTP POST JPEG) ──> [ Central FastAPI Hub ]
  - Camera Capture (Webcam / Stream)                                - Fast HOG Detection (CPU-Optimized)
  - 640x480 Frame Compression                                       - In-Memory 128-d Vector Matcher
  - Real-Time HUD Overlay                                           - 5-Min Cooldown Deduplication
                                                                    - SQLite Database (attendance.db)
                                                                    - Dark/Glassmorphic Web Dashboard
                                                                    - Real-Time SSE Live Stream
```

- **Edge Nodes (`src/nodes/pi_zero_simulator.py`):** Lightweight capture nodes that stream JPEG frames with node metadata to the backend.
- **Central Recognition Hub (`src/server/app.py`):** Async FastAPI server with in-memory matrix caching (`numpy.linalg.norm`), multi-pose enrollment, and live web dashboard.
- **Anti-Spoofing & Liveness Layer (`src/core/liveness_detector.py`):** 2D FFT spectral texture check, YCrCb/HSV skin gamut dispersion, and temporal multi-frame sequence tracking rejecting phone screens, tablets, and printed photos.
- **Deduplication Engine (`src/core/attendance_manager.py`):** Sliding cooldown window (default 5 mins) preventing redundant log spam.
- **CPU Optimization:** Scaled HOG detection + native resolution vector extraction enabling ~30+ FPS real-time recognition on standard laptop CPUs without GPU.

---

## 🚀 Quick Start Guide

### 1. Start the Central Attendance Server
```powershell
.\venv\Scripts\python.exe run_server.py
```
- **Web Dashboard:** [http://localhost:8000](http://localhost:8000)
- **Interactive API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

### 2. Enroll Students
#### Option A: Via Browser Web Dashboard (Dual-Mode: Webcam or 3-Photo Batch Upload)
1. Open [http://localhost:8000/enroll](http://localhost:8000/enroll)
2. Choose either:
   - **Live Webcam Guided Capture:** 3-step capture (Frontal, Left Tilt, Right Tilt).
   - **Batch Photo Upload:** Upload **exactly 3 photos** at once for a student profile with immediate vector extraction.

#### Option B: Via Guided Desktop CLI Wizard
```powershell
.\venv\Scripts\python.exe run_enroll.py --camera 0
```

### 3. Testing & Simulation Modes

#### A. Live Webcam Pi Zero Simulator
Simulate a classroom door node streaming live webcam frames:
```powershell
.\venv\Scripts\python.exe run_node.py --node-id "NODE-CLASSROOM-101" --location "Room 101" --fps 2
```

#### B. Pre-Recorded Video File Testing & Evaluation
Test recognition accuracy against pre-recorded classroom video footage:
```powershell
.\venv\Scripts\python.exe run_video_test.py --video "path\to\classroom_footage.mp4" --fps 2
```
*Tracks multiple simultaneous faces, verifies deduplication window, and generates a formatted attendance summary report table.*

---

## 📁 Project Directory Structure

```
D:\Attendance System\
├── database/
│   └── attendance.db               # SQLite local database
├── data/
│   ├── faces/                      # Registered student face crops
│   ├── snapshots/                  # Verification audit snapshots
│   └── exports/                    # Generated CSV / Excel reports
├── src/
│   ├── config.py                   # System configurations & thresholds
│   ├── database/
│   │   ├── models.py               # SQLAlchemy ORM models
│   │   └── session.py              # DB engine & session handlers
│   ├── core/
│   │   ├── face_engine.py          # Vector matching & in-memory cache
│   │   ├── attendance_manager.py   # Deduplication & live event broker
│   │   └── camera_utils.py         # Frame compression & quality checks
│   ├── server/
│   │   ├── app.py                  # FastAPI application entry point
│   │   ├── routes/                 # API & view route controllers
│   │   ├── static/                 # CSS/JS frontend assets
│   │   └── templates/              # Jinja2 dashboard templates
│   ├── nodes/
│   │   └── pi_zero_simulator.py    # Edge client simulator
│   └── enrollment/
│       └── enroll_cli.py           # CLI enrollment tool
├── tests/
│   ├── test_system.py              # Automated unit/API tests
│   └── test_face_detection.py      # Vision pipeline tests
├── run_server.py                   # Central server launcher
├── run_node.py                     # Simulator launcher (webcam / video)
├── run_video_test.py               # Dedicated video file evaluation tool
├── run_enroll.py                   # Guided enrollment launcher
└── requirements.txt
```

---

## 🧪 Automated Testing & Selective Execution

The test suite includes **136 tests** across 21 test modules. To avoid slow feedback loops during day-to-day feature development (~130s full run), use the **Selective Test Runner** (`run_tests.py`):

### 1. Targeted Suite Execution (Fast Feedback Loops)
Run only the test modules relevant to the modified domain:
```powershell
# Payroll & Statutory Compliance (~8-10s)
.\venv\Scripts\python.exe run_tests.py --suite payroll

# Attendance, Multi-Shift Scheduling & Overrides (~7-9s)
.\venv\Scripts\python.exe run_tests.py --suite attendance

# Company Locations, Designations & Leave Management (~5-7s)
.\venv\Scripts\python.exe run_tests.py --suite masters

# Multi-Tenant Auth, Token Gateways & Portals (~6-8s)
.\venv\Scripts\python.exe run_tests.py --suite auth

# UI Dashboard Layout & Templates (~3-5s)
.\venv\Scripts\python.exe run_tests.py --suite ui

# Computer Vision & dlib HOG Pipeline (~3-5s)
.\venv\Scripts\python.exe run_tests.py --suite cv
```

### 2. Fast Modular Suite (Excludes Heavy Monolith)
Runs all 20 modular test files in **~15-20s**:
```powershell
.\venv\Scripts\python.exe run_tests.py --quick
```

### 3. File Pattern Matching & Fast-Fail Mode
```powershell
# Run only test files matching a specific pattern (e.g. location or payroll)
.\venv\Scripts\python.exe run_tests.py --file location

# Fast-fail mode: stop immediately on first error
.\venv\Scripts\python.exe run_tests.py --suite payroll --failfast
```

### 4. Pre-Deployment Full Test Gate
Reserved for pre-deployment validation to execute all 136 tests across all 21 modules:
```powershell
.\venv\Scripts\python.exe run_tests.py --full
```

### 5. Automated Database Hygiene
All `run_tests.py` runs automatically purge temporary test records and mock tenants upon completion, guaranteeing zero database residues.

