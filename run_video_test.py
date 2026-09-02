import argparse
import os
from pathlib import Path
import sys
import time
from typing import Dict, List, Any
import cv2
import numpy as np
import requests

# Base setup
BASE_DIR = Path(__file__).resolve().parent
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

from src.config import SERVER_PORT, DEFAULT_NODE_ID


class VideoTestRunner:
    """
    Video File Evaluation & Testing Engine.
    Streams pre-recorded video frames through the central face recognition hub,
    tracks multiple simultaneous faces, verifies deduplication cooldown,
    and produces a structured attendance summary report.
    """

    def __init__(
        self,
        video_path: str,
        server_url: str = f"http://localhost:{SERVER_PORT}/api/v1/nodes/frame",
        node_id: str = "NODE-VIDEO-EVAL",
        location: str = "Video Testing Room",
        target_fps: float = 2.0,
        show_window: bool = True,
    ):
        self.video_path = video_path
        self.server_url = server_url
        self.node_id = node_id
        self.location = location
        self.target_fps = target_fps
        self.show_window = show_window

        # Analytics tracking
        self.total_frames_processed = 0
        self.total_detections_count = 0
        self.unique_students_logged: Dict[str, Dict[str, Any]] = {}
        self.unknown_faces_count = 0
        self.start_time = 0.0

    def run(self):
        """Runs the video evaluation test loop."""
        if not os.path.exists(self.video_path):
            print(f"[!] ERROR: Video file not found at: {self.video_path}")
            return

        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            print(f"[!] ERROR: Could not open video file: {self.video_path}")
            return

        total_video_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        duration_sec = round(total_video_frames / video_fps, 1)

        print("==================================================================")
        print("         FACE RECOGNITION VIDEO FILE TESTING & EVALUATION         ")
        print("==================================================================")
        print(f"[*] Video File      : {self.video_path}")
        print(f"[*] Total Frames    : {total_video_frames} (~{duration_sec}s @ {video_fps:.1f} fps)")
        print(f"[*] Processing Rate : {self.target_fps} FPS (Thin-Client Sampling)")
        print(f"[*] Server Endpoint : {self.server_url}")
        print(f"[*] Node ID         : {self.node_id}")
        print(f"[*] Controls        : Press SPACE to Pause | Press 'q' to Quit")
        print("==================================================================\n")

        if self.show_window:
            window_name = f"Video Evaluation - {os.path.basename(self.video_path)}"
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(window_name, 900, 650)

        self.start_time = time.time()
        frame_interval = 1.0 / self.target_fps
        last_frame_time = 0.0
        current_frame_idx = 0
        last_server_response = None
        last_latency_ms = 0.0
        paused = False

        try:
            while cap.isOpened():
                if not paused:
                    ret, frame = cap.read()
                    if not ret:
                        print("[*] Reached end of video file.")
                        break

                    current_frame_idx += 1
                    current_time = time.time()

                    # Sample frame at target FPS
                    if (current_time - last_frame_time) >= frame_interval:
                        last_frame_time = current_time
                        self.total_frames_processed += 1

                        # Resize and compress frame
                        h, w = frame.shape[:2]
                        if w > 640 or h > 480:
                            scale = min(640 / w, 480 / h)
                            send_frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
                        else:
                            send_frame = frame

                        success, buffer = cv2.imencode(".jpg", send_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                        if success:
                            try:
                                req_t0 = time.time()
                                files = {"frame": ("frame.jpg", buffer.tobytes(), "image/jpeg")}
                                data = {"node_id": self.node_id, "location": self.location}

                                resp = requests.post(self.server_url, files=files, data=data, timeout=5.0)
                                last_latency_ms = round((time.time() - req_t0) * 1000, 1)

                                if resp.status_code == 200:
                                    last_server_response = resp.json()
                                    self._record_results(last_server_response, current_frame_idx)
                                else:
                                    print(f"[!] Server returned HTTP {resp.status_code}")
                            except requests.exceptions.RequestException as e:
                                print(f"[!] Server connection error: {e}")

                if self.show_window:
                    display = self._render_video_overlays(
                        frame.copy() if ret else np.zeros((480, 640, 3), dtype=np.uint8),
                        last_server_response,
                        current_frame_idx,
                        total_video_frames,
                        last_latency_ms,
                        paused,
                    )
                    cv2.imshow(window_name, display)

                    key = cv2.waitKey(1 if not paused else 50) & 0xFF
                    if key == ord("q") or key == 27:
                        print("[*] User interrupted video evaluation.")
                        break
                    elif key == ord(" "):
                        paused = not paused
                        print(f"[*] Playback {'PAUSED' if paused else 'RESUMED'}")

        finally:
            cap.release()
            if self.show_window:
                cv2.destroyAllWindows()
            self._print_summary_report()

    def _record_results(self, response: Dict[str, Any], frame_idx: int):
        """Processes and logs server detection results for the final report."""
        results = response.get("results", [])
        self.total_detections_count += len(results)

        for res in results:
            is_match = res.get("is_match", False)
            if is_match:
                roll = res.get("roll_number")
                name = res.get("name")
                conf = res.get("confidence_pct", 0.0)
                logged = res.get("attendance_logged", False)

                if roll not in self.unique_students_logged:
                    self.unique_students_logged[roll] = {
                        "name": name,
                        "roll_number": roll,
                        "department": res.get("department", "N/A"),
                        "first_seen_frame": frame_idx,
                        "first_seen_time": round(time.time() - self.start_time, 1),
                        "max_confidence": conf,
                        "total_frames_seen": 1,
                        "attendance_logged": logged,
                    }
                    print(f"  [+] DETECTED & LOGGED: {name} ({roll}) | Conf: {conf}% | Frame #{frame_idx}")
                else:
                    rec = self.unique_students_logged[roll]
                    rec["total_frames_seen"] += 1
                    if conf > rec["max_confidence"]:
                        rec["max_confidence"] = conf
                    if logged:
                        rec["attendance_logged"] = True
            else:
                self.unknown_faces_count += 1

    def _render_video_overlays(
        self,
        frame: np.ndarray,
        response: Any,
        frame_idx: int,
        total_frames: int,
        latency_ms: float,
        paused: bool,
    ) -> np.ndarray:
        """Renders bounding boxes and HUD stats on the video preview."""
        h, w = frame.shape[:2]

        # Draw detected faces
        if response and "results" in response:
            for res in response.get("results", []):
                box = res.get("box")
                if not box:
                    continue

                top, right, bottom, left = box["top"], box["right"], box["bottom"], box["left"]
                is_match = res.get("is_match", False)
                name = res.get("name", "Unknown")
                roll = res.get("roll_number", "")
                conf = res.get("confidence_pct", 0.0)
                attend_logged = res.get("attendance_logged", False)
                is_live = res.get("is_live", True)
                temp_status = res.get("temporal_status", "REAL")

                if not is_live or temp_status == "SPOOF_DETECTED":
                    color = (0, 0, 255)
                    label = f"[SPOOF DETECTED] Photo/Screen"
                elif temp_status.startswith("VERIFYING"):
                    color = (0, 200, 255)
                    label = f"[{temp_status}] {name}"
                elif is_match:
                    color = (0, 255, 0) if attend_logged else (255, 200, 0)
                    label = f"[REAL {conf}%] {name} ({roll})"
                else:
                    color = (180, 180, 180)
                    label = f"Unknown [{conf}%]"

                # Bounding Box
                thickness = 3 if not is_live else 2
                cv2.rectangle(frame, (left, top), (right, bottom), color, thickness)

                # Label Badge
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.48, 2)
                cv2.rectangle(frame, (left, max(0, top - th - 8)), (left + tw + 6, max(th + 8, top)), color, cv2.FILLED)
                cv2.putText(
                    frame,
                    label,
                    (left + 3, max(th + 2, top - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.48,
                    (255, 255, 255) if color in [(0, 0, 255), (180, 180, 180)] else (0, 0, 0),
                    1,
                    cv2.LINE_AA,
                )

        # Top HUD Banner
        cv2.rectangle(frame, (0, 0), (w, 36), (15, 20, 30), cv2.FILLED)
        pct = round((frame_idx / max(1, total_frames)) * 100, 1)
        status_str = "PAUSED" if paused else f"Frame {frame_idx}/{total_frames} ({pct}%)"
        
        cv2.putText(
            frame,
            f"VIDEO EVAL: {os.path.basename(self.video_path)} | {status_str}",
            (10, 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (220, 220, 220),
            1,
            cv2.LINE_AA,
        )

        hud_right = f"Latency: {latency_ms}ms | Unique: {len(self.unique_students_logged)}"
        (rw, _), _ = cv2.getTextSize(hud_right, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.putText(
            frame,
            hud_right,
            (w - rw - 10, 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 255),
            1,
            cv2.LINE_AA,
        )

        return frame

    def _print_summary_report(self):
        """Prints a comprehensive terminal table report of video evaluation results."""
        elapsed = round(time.time() - self.start_time, 2)
        print("\n==================================================================")
        print("                VIDEO EVALUATION ATTENDANCE REPORT                ")
        print("==================================================================")
        print(f"Total Video Frames Processed : {self.total_frames_processed}")
        print(f"Total Face Detections (All)  : {self.total_detections_count}")
        print(f"Unknown Face Detections      : {self.unknown_faces_count}")
        print(f"Unique Registered Students   : {len(self.unique_students_logged)}")
        print(f"Total Evaluation Time        : {elapsed} seconds")
        print("------------------------------------------------------------------")
        print(f"{'ROLL NUMBER':<16} | {'STUDENT NAME':<22} | {'MAX CONF':<10} | {'FRAMES':<8} | {'STATUS'}")
        print("-" * 66)

        if self.unique_students_logged:
            for roll, data in self.unique_students_logged.items():
                status_str = "PRESENT (LOGGED)" if data["attendance_logged"] else "VERIFIED"
                print(
                    f"{roll:<16} | {data['name']:<22} | {data['max_confidence']:>7.1f}%   | {data['total_frames_seen']:<8} | {status_str}"
                )
        else:
            print("No registered students were recognized in this video.")

        print("==================================================================\n")


def main():
    parser = argparse.ArgumentParser(description="Evaluate attendance recognition on pre-recorded video footage")
    parser.add_argument("--video", type=str, required=True, help="Path to input video file (.mp4, .avi, .mkv)")
    parser.add_argument("--server", type=str, default=f"http://localhost:{SERVER_PORT}/api/v1/nodes/frame", help="Backend ingestion endpoint")
    parser.add_argument("--node-id", type=str, default="NODE-VIDEO-TEST", help="Node Device ID")
    parser.add_argument("--fps", type=float, default=2.0, help="Frame sampling rate (FPS)")
    parser.add_argument("--no-window", action="store_true", help="Disable visual preview window (headless evaluation)")

    args = parser.parse_args()

    runner = VideoTestRunner(
        video_path=args.video,
        server_url=args.server,
        node_id=args.node_id,
        target_fps=args.fps,
        show_window=not args.no_window,
    )
    runner.run()


if __name__ == "__main__":
    main()
