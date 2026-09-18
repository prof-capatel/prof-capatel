import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Ensure DLL path for Anaconda OpenSSL
anaconda_bin = r"C:\ProgramData\Anaconda3\Library\bin"
if os.path.exists(anaconda_bin):
    try:
        os.add_dll_directory(anaconda_bin)
    except Exception:
        pass
    if anaconda_bin not in os.environ.get("PATH", ""):
        os.environ["PATH"] = anaconda_bin + os.pathsep + os.environ.get("PATH", "")

import unittest
import numpy as np
import cv2
import face_recognition

from src.core.face_engine import FaceEngine
from src.database.session import init_db, get_db_context
from src.database.models import Student, FaceEncoding


class TestFaceDetectionPipeline(unittest.TestCase):

    def test_face_recognition_core_availability(self):
        """Verify dlib HOG detector and face model weights."""
        # Create a dummy image (e.g. 300x300 RGB)
        img = np.zeros((300, 300, 3), dtype=np.uint8)
        locations = face_recognition.face_locations(img, model="hog")
        self.assertEqual(len(locations), 0)
        print("[PASS] dlib HOG face location detector verified.")

    def test_pipeline_with_test_profile(self):
        """Verify FaceEngine detection & recognition on blank frame."""
        engine = FaceEngine()
        engine.initialize()
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        results = engine.detect_and_recognize_faces(frame)
        self.assertEqual(len(results), 0)
        print("[PASS] FaceEngine frame pipeline handled empty frame gracefully.")


if __name__ == "__main__":
    unittest.main()
