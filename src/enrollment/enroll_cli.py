import argparse
from datetime import datetime
import sys
import time
import cv2
import numpy as np

from src.config import FACES_DIR, ENROLLMENT_SAMPLES_REQUIRED
from src.core.camera_utils import evaluate_image_quality
from src.core.face_engine import face_engine, FaceEngine
from src.database.models import Student, FaceEncoding
from src.database.session import get_db_context, init_db


def run_enrollment_wizard(camera_index: int = 0):
    """Interactive guided 3-pose face enrollment wizard."""
    init_db()

    print("==========================================================")
    print("      STUDENT FACE ENROLLMENT WIZARD (MULTI-POSE)         ")
    print("==========================================================")

    # 1. Collect student info
    roll_number = input("[?] Enter Student Roll Number (e.g. CS202601): ").strip().upper()
    if not roll_number:
        print("[!] Roll Number cannot be empty.")
        return

    # Check if student exists or create
    with get_db_context() as db:
        student = db.query(Student).filter(Student.roll_number == roll_number).first()
        if student:
            print(f"[*] Found existing student: {student.name} ({student.department})")
            choice = input("[?] Add more face samples to this student? (y/n): ").strip().lower()
            if choice != 'y':
                return
            student_id = student.id
            student_name = student.name
        else:
            name = input("[?] Enter Full Name: ").strip()
            if not name:
                print("[!] Name cannot be empty.")
                return
            department = input("[?] Enter Department [default: Computer Science]: ").strip() or "Computer Science"
            email = input("[?] Enter Email (optional): ").strip() or None

            new_student = Student(
                roll_number=roll_number,
                name=name,
                department=department,
                email=email,
            )
            db.add(new_student)
            db.flush()
            student_id = new_student.id
            student_name = new_student.name
            db.commit()
            print(f"[+] Student registered with ID #{student_id}")

    # 2. Setup Camera
    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"[!] Error: Could not open camera {camera_index}. Please check if camera is in use by another program.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    poses = [
        {"angle": "frontal", "title": "FRONTAL POSE", "instruction": "Look directly at the camera."},
        {"angle": "left", "title": "LEFT TILT (~15deg)", "instruction": "Turn your head slightly to the left."},
        {"angle": "right", "title": "RIGHT TILT (~15deg)", "instruction": "Turn your head slightly to the right."},
    ]

    print("\n[*] Starting camera capture.")
    print("[*] Controls: Press SPACEBAR to capture sample | Press 'q' to cancel.")

    cv2.namedWindow("Student Face Enrollment", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Student Face Enrollment", 800, 600)

    captured_samples = []

    try:
        for idx, pose in enumerate(poses):
            captured = False
            feedback_msg = "Align your face inside frame"
            is_valid_face = False
            last_box = None

            while not captured:
                ret, frame = cap.read()
                if not ret:
                    time.sleep(0.1)
                    continue

                display = frame.copy()
                h, w = display.shape[:2]

                # Fast single face check for HUD guide
                try:
                    vector, face_box, msg = FaceEngine.compute_single_face_vector(frame)
                    if vector is not None and face_box is not None:
                        is_valid_face = True
                        last_box = face_box
                        top, right, bottom, left = face_box
                        # Green guide box
                        cv2.rectangle(display, (left, top), (right, bottom), (0, 255, 0), 2)
                        feedback_msg = "Face detected! Press SPACEBAR to capture."
                    else:
                        is_valid_face = False
                        feedback_msg = msg
                except Exception as e:
                    feedback_msg = "Evaluating frame..."

                # Render Top HUD Banner
                cv2.rectangle(display, (0, 0), (w, 75), (25, 25, 25), cv2.FILLED)
                cv2.putText(
                    display,
                    f"STUDENT: {student_name} ({roll_number}) - STEP {idx + 1}/3: {pose['title']}",
                    (15, 25),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (0, 255, 255),
                    2,
                    cv2.LINE_AA,
                )
                cv2.putText(
                    display,
                    f"Instruction: {pose['instruction']}",
                    (15, 48),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (200, 200, 200),
                    1,
                    cv2.LINE_AA,
                )
                
                # Bottom Status Bar
                status_bg_color = (0, 120, 0) if is_valid_face else (0, 0, 150)
                cv2.rectangle(display, (0, h - 35), (w, h), status_bg_color, cv2.FILLED)
                cv2.putText(
                    display,
                    feedback_msg,
                    (15, h - 12),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (255, 255, 255),
                    1,
                    cv2.LINE_AA,
                )

                cv2.imshow("Student Face Enrollment", display)
                key = cv2.waitKey(1) & 0xFF

                if key == ord(" ") and is_valid_face:
                    # Capture sample
                    is_good, q_msg = evaluate_image_quality(frame)
                    if not is_good:
                        print(f"[!] Quality warning: {q_msg}. Retrying...")
                        continue

                    # Extract final vector
                    vector, face_box, msg = FaceEngine.compute_single_face_vector(frame)
                    if vector is not None and face_box is not None:
                        top, right, bottom, left = face_box
                        pad_h = int((bottom - top) * 0.15)
                        pad_w = int((right - left) * 0.15)
                        c_top = max(0, top - pad_h)
                        c_bottom = min(h, bottom + pad_h)
                        c_left = max(0, left - pad_w)
                        c_right = min(w, right + pad_w)
                        face_crop = frame[c_top:c_bottom, c_left:c_right]

                        filename = f"std_{roll_number}_{pose['angle']}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.jpg"
                        filepath = FACES_DIR / filename
                        cv2.imwrite(str(filepath), face_crop)

                        captured_samples.append({
                            "angle": pose["angle"],
                            "vector": vector,
                            "photo_path": f"faces/{filename}",
                        })
                        print(f"[+] Sample {idx + 1}/3 ({pose['angle']}) captured successfully!")
                        captured = True
                        # Brief visual flash
                        flash = np.full((h, w, 3), 255, dtype=np.uint8)
                        cv2.imshow("Student Face Enrollment", flash)
                        cv2.waitKey(150)
                elif key == ord("q") or key == 27:
                    print("[*] Enrollment cancelled by user.")
                    return

        # Save all captured samples to database
        with get_db_context() as db:
            for s in captured_samples:
                enc = FaceEncoding.from_numpy(
                    student_id=student_id,
                    vector=s["vector"],
                    sample_angle=s["angle"],
                    photo_path=s["photo_path"],
                )
                db.add(enc)
            db.commit()
            # Hot-reload in-memory FaceEngine cache
            face_engine.reload_cache(db)

        print("\n==========================================================")
        print(f"[SUCCESS] Face enrollment complete for {student_name} ({roll_number})!")
        print(f"Total samples enrolled: {len(captured_samples)}")
        print("In-memory recognition cache refreshed.")
        print("==========================================================\n")

    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Guided Face Enrollment Tool")
    parser.add_argument("--camera", type=int, default=0, help="Camera index (default 0)")
    args = parser.parse_args()
    run_enrollment_wizard(camera_index=args.camera)
