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
    print("need opencv - pip install opencv-python")
    sys.exit(1)

MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
MODEL_PATH = Path("models/hand_landmarker.task")


def parse_args():
    p = argparse.ArgumentParser(description="webcam preview with optional gesture shutdown")
    p.add_argument("--camera", type=int, default=0)
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=720)
    p.add_argument("--no-mirror", action="store_true")
    p.add_argument("--no-shutdown", dest="no_shutdown", action="store_true",
                   help="disable the peace-sign shutdown (it's on by default)")
    p.add_argument("--gesture-hold-seconds", type=float, default=4.0)
    p.add_argument("--shutdown-delay-seconds", type=int, default=5)
    return p.parse_args()


# checks index+middle up, ring+pinky down basically
def is_peace_sign(landmarks):
    if len(landmarks) <= 20:
        return False

    fingers = {
        "index": (8, 6),
        "middle": (12, 10),
        "ring": (16, 14),
        "pinky": (20, 18),
    }

    up = {}
    down = {}
    for name, (tip, pip) in fingers.items():
        up[name] = landmarks[tip].y < landmarks[pip].y - 0.02
        down[name] = landmarks[tip].y > landmarks[pip].y + 0.02

    return up["index"] and up["middle"] and down["ring"] and down["pinky"]


def get_model():
    if MODEL_PATH.exists():
        return MODEL_PATH
    print("grabbing the hand landmark model, one sec...")
    MODEL_PATH.parent.mkdir(exist_ok=True)
    urlretrieve(MODEL_URL, MODEL_PATH)
    return MODEL_PATH


def setup_hand_tracker():
    try:
        import mediapipe as mp
        from mediapipe.tasks import python as mp_tasks
        from mediapipe.tasks.python import vision
        from mediapipe.tasks.python.vision import hand_landmarker
    except ModuleNotFoundError:
        print("mediapipe not installed - pip install mediapipe")
        return None

    try:
        model_path = get_model()
    except OSError as e:
        print(f"couldn't download model: {e}")
        print(f"grab it manually and put it at {MODEL_PATH}")
        return None

    opts = vision.HandLandmarkerOptions(
        base_options=mp_tasks.BaseOptions(model_asset_path=str(model_path)),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.7,
        min_hand_presence_confidence=0.7,
        min_tracking_confidence=0.7,
    )

    tracker = vision.HandLandmarker.create_from_options(opts)
    connections = hand_landmarker.HandLandmarksConnections.HAND_CONNECTIONS
    return mp, tracker, connections


def draw_landmarks(frame, landmarks, connections):
    h, w = frame.shape[:2]
    pts = [(int(l.x * w), int(l.y * h)) for l in landmarks]

    for c in connections:
        cv2.line(frame, pts[c.start], pts[c.end], (80, 220, 255), 2, cv2.LINE_AA)
    for pt in pts:
        cv2.circle(frame, pt, 4, (0, 255, 0), -1, cv2.LINE_AA)


def shutdown_windows(delay):
    subprocess.run(["shutdown", "/s", "/t", str(max(0, delay))], check=False)


def main():
    args = parse_args()
    shutdown_armed = not args.no_shutdown

    if shutdown_armed and not sys.platform.startswith("win"):
        print("gesture shutdown only works on windows, sorry - running without it")
        shutdown_armed = False

    # dshow tends to open faster on windows
    cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW) if sys.platform.startswith("win") else cv2.VideoCapture(args.camera)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    if not cap.isOpened():
        print(f"couldn't open camera {args.camera}")
        return 1

    win_name = "webcam - q/esc to quit, s to save"
    last_time = time.perf_counter()
    gesture_start = None
    shutdown_fired = False
    fps = 0.0

    print("q or esc quits, s saves a snapshot")
    if shutdown_armed:
        print(f"shutdown armed - hold the peace sign for {args.gesture_hold_seconds:.1f}s to trigger it")

    mp_module = tracker = connections = None
    if shutdown_armed:
        result = setup_hand_tracker()
        if result is None:
            cap.release()
            cv2.destroyAllWindows()
            return 1
        mp_module, tracker, connections = result

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("lost the camera feed")
                return 1

            if not args.no_mirror:
                frame = cv2.flip(frame, 1)

            now = time.perf_counter()
            dt = now - last_time
            last_time = now
            if dt > 0:
                fps = 0.9 * fps + 0.1 * (1.0 / dt)

            peace_sign_now = False
            if tracker is not None:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp_module.Image(image_format=mp_module.ImageFormat.SRGB, data=rgb)
                results = tracker.detect_for_video(mp_image, int(now * 1000))

                if results.hand_landmarks:
                    hand = results.hand_landmarks[0]
                    draw_landmarks(frame, hand, connections)
                    peace_sign_now = is_peace_sign(hand)

                if peace_sign_now:
                    if gesture_start is None:
                        gesture_start = now

                    held = now - gesture_start
                    remaining = args.gesture_hold_seconds - held

                    if held >= args.gesture_hold_seconds and not shutdown_fired:
                        shutdown_fired = True
                        print(f"gesture held long enough, shutting down in {args.shutdown_delay_seconds}s")
                        shutdown_windows(args.shutdown_delay_seconds)
                        break

                    cv2.putText(frame, f"Shutdown in {max(0.0, remaining):.1f}s", (20, 80),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2, cv2.LINE_AA)
                else:
                    gesture_start = None

            cv2.putText(frame, f"Camera {args.camera} | FPS {fps:.1f}", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2, cv2.LINE_AA)

            cv2.imshow(win_name, frame)
            key = cv2.waitKey(1) & 0xFF

            if key in (ord("q"), 27):
                break
            if cv2.getWindowProperty(win_name, cv2.WND_PROP_VISIBLE) < 1:
                break
            if key == ord("s"):
                out_dir = Path("snapshots")
                out_dir.mkdir(exist_ok=True)
                fname = out_dir / f"webcam_{datetime.now():%Y%m%d_%H%M%S}.png"
                cv2.imwrite(str(fname), frame)
                print(f"saved {fname}")
    finally:
        if tracker is not None:
            tracker.close()
        cap.release()
        cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    sys.exit(main())