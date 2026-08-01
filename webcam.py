
from __future__ import annotations 
import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.request import urlretrieve

try:
    import cv2
except ModuleNotFoundError:
    print("OpenCV is not installed. Install it with: pip install opencv-python")
    sys.exit(1)

FINGER_TIP_AND_PIP = {
    "index": (8, 6),
    "ok_sign": (12, 10),
    "ring": (16, 14),
    "pinky": (20, 18),
}

HAND_LANDMARKER_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)
HAND_LANDMARKER_MODEL_PATH = Path("models/hand_landmarker.task")


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
        "--shutdown-on-ok-sign",
        dest="shutdown_on_ok_sign",
        action="store_true",
        help="Arm Windows shutdown when an OK-sign-only gesture is held.",
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


def is_ok_sign_finger_only(landmarks) -> bool:
    if len(landmarks) <= 20:
        return False

    tip_to_pip = {
        "index": (8, 6),
        "middle": (12, 10),
        "ring": (16, 14),
        "pinky": (20, 18),
    }

    finger_states = {}
    for name, (tip, pip) in tip_to_pip.items():
        finger_states[name] = {
            "tip_above_pip": landmarks[tip].y < landmarks[pip].y - 0.02,
            "tip_below_pip": landmarks[tip].y > landmarks[pip].y + 0.02,
            "tip_x_close": abs(landmarks[tip].x - landmarks[pip].x) < 0.08,
        }

    middle_finger_bent = (
        finger_states["middle"]["tip_above_pip"]
        and finger_states["middle"]["tip_x_close"]
    )
    index_finger_extended = not finger_states["index"]["tip_above_pip"]
    ring_finger_extended = not finger_states["ring"]["tip_above_pip"]
    pinky_extended = not finger_states["pinky"]["tip_above_pip"]

    return (
        not middle_finger_bent
        and index_finger_extended
        and ring_finger_extended
        and pinky_extended
        and finger_states["middle"]["tip_below_pip"]
    )


def ensure_hand_landmarker_model() -> Path:
    if HAND_LANDMARKER_MODEL_PATH.exists():
        return HAND_LANDMARKER_MODEL_PATH

    print("Downloading MediaPipe hand landmark model...")
    HAND_LANDMARKER_MODEL_PATH.parent.mkdir(exist_ok=True)
    urlretrieve(HAND_LANDMARKER_MODEL_URL, HAND_LANDMARKER_MODEL_PATH)
    return HAND_LANDMARKER_MODEL_PATH


def create_hand_tracker():
    try:
        import mediapipe as mp
        from mediapipe.tasks import python as mp_tasks_python
        from mediapipe.tasks.python import vision
        from mediapipe.tasks.python.vision import hand_landmarker
    except ModuleNotFoundError:
        print("MediaPipe is not installed. Install it with: pip install mediapipe")
        return None

    try:
        model_path = ensure_hand_landmarker_model()
    except OSError as exc:
        print(f"Could not download the MediaPipe hand model: {exc}")
        print(f"Download it manually and save it as: {HAND_LANDMARKER_MODEL_PATH}")
        return None

    options = vision.HandLandmarkerOptions(
        base_options=mp_tasks_python.BaseOptions(model_asset_path=str(model_path)),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.7,
        min_hand_presence_confidence=0.7,
        min_tracking_confidence=0.7,
    )

    tracker = vision.HandLandmarker.create_from_options(options)
    connections = hand_landmarker.HandLandmarksConnections.HAND_CONNECTIONS
    return mp, tracker, connections


def draw_hand_landmarks(frame, landmarks, connections) -> None:
    height, width = frame.shape[:2]
    points = [
        (int(landmark.x * width), int(landmark.y * height))
        for landmark in landmarks
    ]

    for connection in connections:
        cv2.line(
            frame,
            points[connection.start],
            points[connection.end],
            (80, 220, 255),
            2,
            cv2.LINE_AA,
        )

    for point in points:
        cv2.circle(frame, point, 4, (0, 255, 0), -1, cv2.LINE_AA)


def schedule_windows_shutdown(delay_seconds: int) -> None:
    subprocess.run(
        ["shutdown", "/s", "/t", str(max(0, delay_seconds))],
        check=False,
    )


def main() -> int:
    args = parse_args()
    mediapipe_module = None
    hand_connections = None
    shutdown_on_gesture = bool(getattr(args, "shutdown_on_ok_sign", False))

    if shutdown_on_gesture:
        if not sys.platform.startswith("win"):
            print("Automatic shutdown is only configured for Windows.")
            return 1

    if sys.platform.startswith("win"):
        capture = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    else:
        capture = cv2.VideoCapture(args.camera)
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
    if shutdown_on_gesture:
        print(
            "Shutdown armed. Hold an OK sign gesture "
            f"for {args.gesture_hold_seconds:.1f} seconds to trigger it."
        )

    hand_tracker = None
    if shutdown_on_gesture:
        tracker_parts = create_hand_tracker()
        if tracker_parts is None:
            capture.release()
            cv2.destroyAllWindows()
            return 1
        mediapipe_module, hand_tracker, hand_connections = tracker_parts

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

            ok_sign_finger_detected = False
            if (
                hand_tracker is not None
                and mediapipe_module is not None
                and hand_connections is not None
            ):
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mediapipe_module.Image(
                    image_format=mediapipe_module.ImageFormat.SRGB,
                    data=rgb_frame,
                )
                timestamp_ms = int(now * 1000)
                results = hand_tracker.detect_for_video(mp_image, timestamp_ms)

                if results.hand_landmarks:
                    hand_landmarks = results.hand_landmarks[0]
                    draw_hand_landmarks(frame, hand_landmarks, hand_connections)
                    ok_sign_finger_detected = is_ok_sign_finger_only(hand_landmarks)

                if ok_sign_finger_detected:
                    if gesture_started_at is None:
                        gesture_started_at = now

                    held_seconds = now - gesture_started_at
                    remaining_seconds = args.gesture_hold_seconds - held_seconds

                    if held_seconds >= args.gesture_hold_seconds and not shutdown_sent:
                        shutdown_sent = True
                        print(
                            "OK sign gesture confirmed. "
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

            if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
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