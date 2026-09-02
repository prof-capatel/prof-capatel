import argparse
import sys
import time
from typing import Optional
import cv2
import numpy as np
import requests

from src.config import (
    DEFAULT_NODE_ID,
    DEFAULT_NODE_LOCATION,
    DEFAULT_NODE_FPS,
    SERVER_HOST,
    SERVER_PORT,
)


class PiZeroSimulator:
    """
    Classroom Simulation Node mimicking a Raspberry Pi Zero thin-client.
    Captures camera frames, compresses to JPEG, and dispatches HTTP POST payloads
    to the Central Matching Server. Overlays server recognition response on display.
    """

    def __init__(
        self,
        server_url: str,
        node_id: str = DEFAULT_NODE_ID,
        location: str = DEFAULT_NODE_LOCATION,
        target_fps: float = DEFAULT_NODE_FPS,
        camera_index: int = 0,
        video_source: Optional[str] = None,
    ):
        self.server_url = server_url
        self.node_id = node_id
        self.location = location
        self.target_fps = target_fps
        self.camera_index = camera_index
        self.video_source = video_source
        self.running = False

    def _open_camera(self):
        """Attempts to open camera using DirectShow (Windows) or default backend."""
        source = self.video_source if self.video_source else self.camera_index
        if isinstance(source, int):
            # On Windows, DirectShow (CAP_DSHOW) resolves MSMF lock issues and is much more reliable
            cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
            if not cap.isOpened():
                # Fallback to default backend
                cap = cv2.VideoCapture(source)
        else:
            cap = cv2.VideoCapture(source)

        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            # Ensure buffer size is 1 to avoid frame lag
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return cap

    def start(self):
        """Starts video capture and real-time streaming loop with auto-reconnect."""
        source = self.video_source if self.video_source else self.camera_index
        print(f"[*] Initializing Video Source: {source}")
        
        cap = self._open_camera()

        self.running = True
        frame_interval = 1.0 / self.target_fps
        last_frame_time = 0.0

        last_server_response = None
        last_latency_ms = 0.0
        server_status = "CONNECTING"
        retry_delay = 2.0
        last_retry_time = 0.0

        print(f"==========================================================")
        print(f"[*] PI ZERO SIMULATOR NODE STARTED")
        print(f"[*] Node ID     : {self.node_id}")
        print(f"[*] Location    : {self.location}")
        print(f"[*] Target FPS  : {self.target_fps}")
        print(f"[*] Server URL  : {self.server_url}")
        print(f"[*] Press 'q' in video window to exit.")
        print(f"==========================================================")

        cv2.namedWindow(f"Pi Zero Edge Node - {self.node_id}", cv2.WINDOW_NORMAL)
        cv2.resizeWindow(f"Pi Zero Edge Node - {self.node_id}", 800, 600)

        try:
            while self.running:
                loop_start = time.time()

                if not cap.isOpened():
                    current_time = time.time()
                    if current_time - last_retry_time >= retry_delay:
                        last_retry_time = current_time
                        print("[*] Re-attempting camera connection (Make sure browser / enroll tab released camera)...")
                        cap.release()
                        cap = self._open_camera()

                    # Render standby frame while camera is busy
                    blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                    cv2.putText(
                        blank_frame,
                        "Camera Busy / In Use by Another Process",
                        (40, 220),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 165, 255),
                        2,
                        cv2.LINE_AA,
                    )
                    cv2.putText(
                        blank_frame,
                        "Please close or release the camera in your browser enrollment tab.",
                        (40, 260),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.45,
                        (200, 200, 200),
                        1,
                        cv2.LINE_AA,
                    )
                    cv2.imshow(f"Pi Zero Edge Node - {self.node_id}", blank_frame)
                    key = cv2.waitKey(200) & 0xFF
                    if key == ord("q") or key == 27:
                        break
                    continue

                ret, frame = cap.read()
                if not ret:
                    if self.video_source:  # Loop video file
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    else:
                        print("[!] Camera frame grab failed. Camera may be locked by another application. Re-initializing in 2s...")
                        cap.release()
                        time.sleep(1.0)
                        continue

                current_time = time.time()
                # Check if it's time to send a frame to the server
                if (current_time - last_frame_time) >= frame_interval:
                    last_frame_time = current_time

                    # Compress frame to JPEG for edge transmission efficiency
                    success, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    if success:
                        try:
                            req_start = time.time()
                            files = {"frame": ("frame.jpg", buffer.tobytes(), "image/jpeg")}
                            data = {"node_id": self.node_id, "location": self.location}

                            response = requests.post(
                                self.server_url,
                                files=files,
                                data=data,
                                timeout=3.0,
                            )
                            last_latency_ms = round((time.time() - req_start) * 1000, 1)

                            if response.status_code == 200:
                                last_server_response = response.json()
                                server_status = "ONLINE"
                            else:
                                server_status = f"HTTP {response.status_code}"
                        except requests.exceptions.RequestException as e:
                            server_status = "OFFLINE (Retrying...)"
                            last_latency_ms = 0.0

                # Render overlays on preview frame
                display_frame = self._render_overlays(
                    frame.copy(),
                    last_server_response,
                    server_status,
                    last_latency_ms,
                )

                cv2.imshow(f"Pi Zero Edge Node - {self.node_id}", display_frame)

                # Process keyboard events
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q") or key == 27:  # 'q' or ESC
                    print("[*] Exit signal received. Stopping node simulator...")
                    break

                # Sleep slightly to maintain target rate without pegging CPU
                elapsed = time.time() - loop_start
                sleep_time = max(0.005, (1.0 / 30.0) - elapsed)
                time.sleep(sleep_time)

        finally:
            self.running = False
            cap.release()
            cv2.destroyAllWindows()
            print("[*] Pi Zero Simulator node terminated gracefully.")

    def _render_overlays(
        self,
        frame,
        server_response,
        server_status: str,
        latency_ms: float,
    ):
        """Draws bounding boxes and HUD stats on the simulated node display."""
        h, w = frame.shape[:2]

        # Draw detected face boxes if available
        if server_response and "results" in server_response:
            for res in server_response.get("results", []):
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
                    # Red (Bold): Spoof Attack / Photo Screen Detected
                    color = (0, 0, 255)
                    label = f"[SPOOF DETECTED] Photo / Screen Refused"
                elif temp_status.startswith("VERIFYING"):
                    # Amber/Yellow: Temporal liveness confirmation in progress
                    color = (0, 200, 255)
                    label = f"[{temp_status}] {name}"
                elif is_match:
                    if attend_logged:
                        # Green: Newly marked attendance!
                        color = (0, 255, 0)
                        label = f"[REAL {conf}%] {name} ({roll}) [LOGGED]"
                    else:
                        # Cyan: Match verified (already logged / cooldown active)
                        color = (255, 200, 0)
                        label = f"[REAL {conf}%] {name} ({roll})"
                else:
                    # Gray/Red: Unknown face
                    color = (180, 180, 180)
                    label = f"Unknown Visitor"

                # Draw bounding box
                thickness = 3 if not is_live else 2
                cv2.rectangle(frame, (left, top), (right, bottom), color, thickness)

                # Draw label badge
                label_size, baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.50, 2)
                cv2.rectangle(
                    frame,
                    (left, max(0, top - label_size[1] - 8)),
                    (left + label_size[0] + 6, max(label_size[1] + 8, top)),
                    color,
                    cv2.FILLED,
                )
                cv2.putText(
                    frame,
                    label,
                    (left + 3, max(label_size[1] + 2, top - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.50,
                    (255, 255, 255) if color in [(0, 0, 255), (180, 180, 180)] else (0, 0, 0),
                    1,
                    cv2.LINE_AA,
                )

        # Top HUD Banner
        cv2.rectangle(frame, (0, 0), (w, 36), (20, 20, 20), cv2.FILLED)
        status_color = (0, 255, 0) if "ONLINE" in server_status else (0, 165, 255) if "CONNECTING" in server_status else (0, 0, 255)
        
        cv2.putText(
            frame,
            f"NODE: {self.node_id} | {self.location}",
            (10, 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (220, 220, 220),
            1,
            cv2.LINE_AA,
        )
        
        status_text = f"Server: {server_status} ({latency_ms}ms)"
        text_size, _ = cv2.getTextSize(status_text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        cv2.putText(
            frame,
            status_text,
            (w - text_size[0] - 10, 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            status_color,
            1,
            cv2.LINE_AA,
        )

        return frame


def main():
    parser = argparse.ArgumentParser(description="Classroom Pi Zero Node Simulator")
    parser.add_argument("--server", type=str, default=f"http://localhost:{SERVER_PORT}/api/v1/nodes/frame", help="Backend ingestion endpoint URL")
    parser.add_argument("--node-id", type=str, default=DEFAULT_NODE_ID, help="Node Device ID")
    parser.add_argument("--location", type=str, default=DEFAULT_NODE_LOCATION, help="Classroom Location Name")
    parser.add_argument("--fps", type=float, default=DEFAULT_NODE_FPS, help="Frame transmission rate (FPS)")
    parser.add_argument("--camera", type=int, default=0, help="Webcam device index (default: 0)")
    parser.add_argument("--source", type=str, default=None, help="Optional video file path instead of live webcam")
    parser.add_argument("--video", type=str, default=None, help="Optional video file path alias")

    args = parser.parse_args()
    video_source = args.video if args.video else args.source

    simulator = PiZeroSimulator(
        server_url=args.server,
        node_id=args.node_id,
        location=args.location,
        target_fps=args.fps,
        camera_index=args.camera,
        video_source=video_source,
    )
    simulator.start()


if __name__ == "__main__":
    main()
