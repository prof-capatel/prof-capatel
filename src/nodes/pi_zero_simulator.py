import argparse
import signal
import sys
import threading
import time
from typing import Optional, Union
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
        enable_audio_alert: bool = True,
    ):
        self.server_url = server_url
        self.node_id = node_id
        self.location = location
        self.target_fps = target_fps
        self.camera_index = camera_index
        self.video_source = video_source
        self.enable_audio_alert = enable_audio_alert
        self.running = False
        self._cap: Optional[cv2.VideoCapture] = None
        self._last_logged_time = 0.0
        self._last_logged_name = ""

        # Setup graceful signal handlers
        signal.signal(signal.SIGINT, self._handle_exit_signal)
        signal.signal(signal.SIGTERM, self._handle_exit_signal)

    def _handle_exit_signal(self, signum, frame):
        print("\n[*] Interruption signal received. Releasing camera hardware and exiting...")
        self.running = False
        if self._cap is not None:
            self._cap.release()
        cv2.destroyAllWindows()
        sys.exit(0)

    def _play_audio_chime(self):
        """Plays a gentle high-tech biometric chime in a background thread."""
        if not self.enable_audio_alert:
            return

        def _sound_worker():
            try:
                import winsound
                winsound.Beep(587, 120)
                winsound.Beep(880, 180)
            except Exception:
                # Terminal bell fallback
                sys.stdout.write("\a")
                sys.stdout.flush()

        threading.Thread(target=_sound_worker, daemon=True).start()

    def probe_available_cameras(self) -> Optional[cv2.VideoCapture]:
        """
        Probes camera indices 0..3 across DirectShow and MSMF backends to locate
        the first active, working RGB camera sensor that produces valid frames.
        """
        if self.video_source:
            cap = cv2.VideoCapture(self.video_source)
            if cap.isOpened():
                self._cap = cap
                return cap
            return None

        # Try user-selected index first, followed by others
        candidate_indices = [self.camera_index] + [i for i in [0, 1, 2, 3] if i != self.camera_index]

        for idx in candidate_indices:
            for backend_name, backend_code in [("DirectShow", cv2.CAP_DSHOW), ("MSMF", cv2.CAP_MSMF), ("Default", cv2.CAP_ANY)]:
                try:
                    cap = cv2.VideoCapture(idx, backend_code)
                    if cap.isOpened():
                        ret, frame = cap.read()
                        if ret and frame is not None and frame.size > 0:
                            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                            print(f"[*] Verified active camera hardware: Index #{idx} via {backend_name}.")
                            self.camera_index = idx
                            self._cap = cap
                            return cap
                    cap.release()
                except Exception:
                    pass

        print("[!] No active RGB camera could be opened directly. (Camera may be in use by browser or locked).")
        return None

    def start(self):
        """Starts video capture and real-time streaming loop with auto-reconnect."""
        source_label = self.video_source if self.video_source else f"Camera #{self.camera_index} (Auto-Detect)"
        print(f"[*] Initializing Video Source: {source_label}")

        cap = self.probe_available_cameras()

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
        print(f"[*] Audio Chime : {'ENABLED' if self.enable_audio_alert else 'MUTED'}")
        print(f"[*] Press 'q' or 'ESC' in video window to exit.")
        print(f"==========================================================")

        window_name = f"Pi Zero Edge Node - {self.node_id}"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 800, 600)

        try:
            while self.running:
                loop_start = time.time()

                if cap is None or not cap.isOpened():
                    current_time = time.time()
                    if current_time - last_retry_time >= retry_delay:
                        last_retry_time = current_time
                        print("[*] Probing for available camera device...")
                        if cap is not None:
                            cap.release()
                        cap = self.probe_available_cameras()

                    # Render standby frame while camera is busy
                    blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                    cv2.putText(
                        blank_frame,
                        "Camera Hardware Busy or In Use",
                        (40, 200),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 165, 255),
                        2,
                        cv2.LINE_AA,
                    )
                    cv2.putText(
                        blank_frame,
                        "Please close other apps/browser tabs using webcam.",
                        (40, 240),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.48,
                        (200, 200, 200),
                        1,
                        cv2.LINE_AA,
                    )
                    cv2.imshow(window_name, blank_frame)
                    key = cv2.waitKey(200) & 0xFF
                    if key == ord("q") or key == 27:
                        break
                    continue

                ret, frame = cap.read()
                if not ret or frame is None:
                    if self.video_source:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    else:
                        print("[!] Camera frame grab failed. Retrying probe in 2s...")
                        cap.release()
                        cap = None
                        time.sleep(1.0)
                        continue

                current_time = time.time()
                # Check if it's time to send a frame to the server
                if (current_time - last_frame_time) >= frame_interval:
                    last_frame_time = current_time

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

                                # Check if any student attendance was logged
                                detections = last_server_response.get("detections") or last_server_response.get("results") or []
                                for d in detections:
                                    if d.get("attendance_logged"):
                                        self._last_logged_time = time.time()
                                        self._last_logged_name = d.get("name", "Student")
                                        self._play_audio_chime()
                                        break
                            else:
                                server_status = f"HTTP {response.status_code}"
                        except requests.exceptions.RequestException:
                            server_status = "OFFLINE (Retrying...)"
                            last_latency_ms = 0.0

                # Render overlays on preview frame
                display_frame = self._render_overlays(
                    frame.copy(),
                    last_server_response,
                    server_status,
                    last_latency_ms,
                )

                cv2.imshow(window_name, display_frame)

                key = cv2.waitKey(1) & 0xFF
                if key == ord("q") or key == 27:
                    print("[*] Exit signal received. Stopping node simulator...")
                    break

                elapsed = time.time() - loop_start
                sleep_time = max(0.005, (1.0 / 30.0) - elapsed)
                time.sleep(sleep_time)

        finally:
            self.running = False
            if cap is not None:
                cap.release()
            cv2.destroyAllWindows()
            print("[*] Pi Zero Simulator node terminated gracefully. Camera released.")

    def _render_overlays(
        self,
        frame,
        server_response,
        server_status: str,
        latency_ms: float,
    ):
        """Draws bounding boxes and HUD stats on the simulated node display."""
        h, w = frame.shape[:2]
        now = time.time()

        # 1. Emerald flash border on recent check-in
        if (now - self._last_logged_time) < 1.2:
            cv2.rectangle(frame, (0, 0), (w, h), (0, 255, 0), 8)
            # Floating toast notification at top
            toast_text = f"✓ ATTENDANCE RECORDED: {self._last_logged_name.upper()}"
            t_size, _ = cv2.getTextSize(toast_text, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)
            tx = (w - t_size[0]) // 2
            cv2.rectangle(frame, (tx - 16, 44), (tx + t_size[0] + 16, 78), (0, 180, 0), cv2.FILLED)
            cv2.putText(frame, toast_text, (tx, 68), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)

        # 2. Draw detected face boxes
        detections = []
        if server_response:
            detections = server_response.get("detections") or server_response.get("results") or []

        for res in detections:
            box = res.get("box")
            if not box:
                continue

            top, right, bottom, left = box["top"], box["right"], box["bottom"], box["left"]
            is_match = res.get("is_match", False)
            name = res.get("name", "Unknown")
            roll = res.get("roll_number", "")
            conf = res.get("confidence_pct", 0.0)
            attend_logged = res.get("attendance_logged", False)
            cooldown_active = res.get("cooldown_active", False)
            cooldown_rem = res.get("cooldown_remaining_minutes", 0)
            is_live = res.get("is_live", True)
            temp_status = res.get("temporal_status", "REAL")

            if not is_live or temp_status == "SPOOF_DETECTED":
                color = (0, 0, 255)
                label = f"SPOOF ATTACK REFUSED"
            elif temp_status.startswith("VERIFYING"):
                color = (0, 200, 255)
                label = f"[{temp_status}] {name}"
            elif is_match:
                if attend_logged:
                    color = (0, 255, 0)
                    roll_str = f" ({roll})" if roll and roll != "N/A" else ""
                    label = f"✓ {name}{roll_str} [LOGGED]"
                elif cooldown_active:
                    color = (255, 200, 0)
                    roll_str = f" ({roll})" if roll and roll != "N/A" else ""
                    label = f"✓ {name}{roll_str} [COOLDOWN {cooldown_rem}m]"
                else:
                    color = (255, 200, 0)
                    roll_str = f" ({roll})" if roll and roll != "N/A" else ""
                    label = f"✓ {name}{roll_str} ({conf}%)"
            else:
                color = (180, 180, 180)
                label = "Unknown Visitor"

            # Draw bounding box
            thickness = 3 if not is_live else 2
            cv2.rectangle(frame, (left, top), (right, bottom), color, thickness)

            # Draw label badge directly above bounding box
            label_size, baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.48, 1)
            pill_top = max(38, top - label_size[1] - 8)
            cv2.rectangle(
                frame,
                (left, pill_top),
                (left + label_size[0] + 10, pill_top + label_size[1] + 8),
                color,
                cv2.FILLED,
            )
            cv2.putText(
                frame,
                label,
                (left + 5, pill_top + label_size[1] + 3),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.48,
                (255, 255, 255) if color in [(0, 0, 255), (180, 180, 180)] else (0, 0, 0),
                1,
                cv2.LINE_AA,
            )

        # Top HUD Banner
        cv2.rectangle(frame, (0, 0), (w, 36), (15, 15, 25), cv2.FILLED)
        status_color = (0, 255, 0) if "ONLINE" in server_status else (0, 165, 255) if "CONNECTING" in server_status else (0, 0, 255)

        audio_str = "🔊" if self.enable_audio_alert else "🔇"
        cv2.putText(
            frame,
            f"NODE: {self.node_id} | {self.location} | Cam #{self.camera_index} {audio_str}",
            (10, 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            (220, 220, 220),
            1,
            cv2.LINE_AA,
        )

        status_text = f"Server: {server_status} ({latency_ms}ms)"
        text_size, _ = cv2.getTextSize(status_text, cv2.FONT_HERSHEY_SIMPLEX, 0.50, 1)
        cv2.putText(
            frame,
            status_text,
            (w - text_size[0] - 10, 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
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
    parser.add_argument("--camera", type=int, default=0, help="Webcam device index (default: 0, auto-probed if fails)")
    parser.add_argument("--source", type=str, default=None, help="Optional video file path instead of live webcam")
    parser.add_argument("--video", type=str, default=None, help="Optional video file path alias")
    parser.add_argument("--audio-alert", type=str, default="Y", choices=["Y", "N", "y", "n", "true", "false", "1", "0"], help="Enable attendance check-in audio chime (Y/N, default: Y)")

    args = parser.parse_args()
    video_source = args.video if args.video else args.source
    enable_audio = args.audio_alert.upper() in ["Y", "TRUE", "1"]

    simulator = PiZeroSimulator(
        server_url=args.server,
        node_id=args.node_id,
        location=args.location,
        target_fps=args.fps,
        camera_index=args.camera,
        video_source=video_source,
        enable_audio_alert=enable_audio,
    )
    simulator.start()


if __name__ == "__main__":
    main()
