"""Simple webcam viewer for testing the default camera.

Usage:
    python webcam.py
    python webcam.py --camera 1

Keys:
    q or Esc  Quit
    s         Save a snapshot to ./snapshots
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import cv2
except ModuleNotFoundError:
    print("OpenCV is not installed. Install it with: pip install opencv-python")
    sys.exit(1)

try:
    import mediapipe as mp
except ModuleNotFoundError:
    mp = None


FINGER_TIP_AND_PIP = {
    "index": (8, 6),
    "middle": (12, 10),
    "ring": (16, 14),
    "pinky": (20, 18),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Open a live webcam preview.")
    parser.add_argument(
        "--camera",
        type=int,
        default=0,
        help="Camera index to open. Default: 0",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=1280,
        help="Requested camera width. Default: 1280",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=720,
        help="Requested camera height. Default: 720",
    )
    parser.add_argument(
        "--no-mirror",
        action="store_true",
        help="Disable mirror mode for the preview.",
    )
    parser.add_argument(
        "--shutdown-on-middle-finger",
        action="store_true",
        help="Arm Windows shutdown when a middle-finger-only gesture is held.",
    )
    parser.add_argument(
        "--gesture-hold-seconds",
        type=float,
        default=2.0,
        help="Seconds the gesture must be held before shutdown. Default: 2.0",
    )
    parser.add_argument(
        "--shutdown-delay-seconds",
        type=int,
        default=5,
        help="Windows shutdown countdown after the gesture triggers. Default: 5",
    )
    return parser.parse_args()


def is_middle_finger_only(landmarks) -> bool:
    fingers = {
        name: landmarks[tip].y < landmarks[pip].y - 0.02
        for name, (tip, pip) in FINGER_TIP_AND_PIP.items()
    }

    return (
        fingers["middle"]
        and not fingers["index"]
        and not fingers["ring"]
        and not fingers["pinky"]
    )


def schedule_windows_shutdown(delay_seconds: int) -> None:
    subprocess.run(
        ["shutdown", "/s", "/t", str(max(0, delay_seconds))],
        check=False,
    )


def main() -> int:
    args = parse_args()

    if args.shutdown_on_middle_finger:
        if not sys.platform.startswith("win"):
            print("Automatic shutdown is only configured for Windows.")
            return 1
        if mp is None:
            print("MediaPipe is not installed. Install it with: pip install mediapipe")
            return 1

    capture = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    if not capture.isOpened():
        print(f"Could not open webcam at camera index {args.camera}.")
        print("Try another camera with: python webcam.py --camera 1")
        return 1

    window_name = "Python Webcam - q/Esc to quit, s to save"
    previous_time = time.perf_counter()
    gesture_started_at = None
    shutdown_sent = False
    fps = 0.0

    print("Webcam running. Press q or Esc to quit. Press s to save a snapshot.")
    if args.shutdown_on_middle_finger:
        print(
            "Shutdown armed. Hold a middle-finger-only gesture "
            f"for {args.gesture_hold_seconds:.1f} seconds to trigger it."
        )

    hand_tracker = None
    if args.shutdown_on_middle_finger:
        hand_tracker = mp.solutions.hands.Hands(
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7,
        )

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                print("Could not read a frame from the webcam.")
                return 1

            if not args.no_mirror:
                frame = cv2.flip(frame, 1)

            now = time.perf_counter()
            elapsed = now - previous_time
            previous_time = now
            if elapsed > 0:
                fps = 0.9 * fps + 0.1 * (1.0 / elapsed)

            middle_finger_detected = False
            if hand_tracker is not None:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = hand_tracker.process(rgb_frame)

                if results.multi_hand_landmarks:
                    hand_landmarks = results.multi_hand_landmarks[0]
                    mp.solutions.drawing_utils.draw_landmarks(
                        frame,
                        hand_landmarks,
                        mp.solutions.hands.HAND_CONNECTIONS,
                    )
                    middle_finger_detected = is_middle_finger_only(
                        hand_landmarks.landmark
                    )

                if middle_finger_detected:
                    if gesture_started_at is None:
                        gesture_started_at = now

                    held_seconds = now - gesture_started_at
                    remaining_seconds = args.gesture_hold_seconds - held_seconds

                    if held_seconds >= args.gesture_hold_seconds and not shutdown_sent:
                        shutdown_sent = True
                        print(
                            "Middle finger gesture confirmed. "
                            f"Shutting down in {args.shutdown_delay_seconds} seconds."
                        )
                        schedule_windows_shutdown(args.shutdown_delay_seconds)
                        break

                    cv2.putText(
                        frame,
                        f"Shutdown in {max(0.0, remaining_seconds):.1f}s",
                        (20, 80),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.9,
                        (0, 0, 255),
                        2,
                        cv2.LINE_AA,
                    )
                else:
                    gesture_started_at = None

            cv2.putText(
                frame,
                f"Camera {args.camera} | FPS {fps:.1f}",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )

            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF

            if key in (ord("q"), 27):
                break

            if key == ord("s"):
                snapshots_dir = Path("snapshots")
                snapshots_dir.mkdir(exist_ok=True)
                filename = snapshots_dir / f"webcam_{datetime.now():%Y%m%d_%H%M%S}.png"
                cv2.imwrite(str(filename), frame)
                print(f"Saved snapshot: {filename}")
    finally:
        if hand_tracker is not None:
            hand_tracker.close()
        capture.release()
        cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

