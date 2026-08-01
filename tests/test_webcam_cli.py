import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


def load_webcam_module():
    cv2_stub = types.ModuleType("cv2")
    cv2_stub.CAP_DSHOW = 0
    cv2_stub.CAP_PROP_FRAME_WIDTH = 0
    cv2_stub.CAP_PROP_FRAME_HEIGHT = 0
    cv2_stub.WND_PROP_VISIBLE = 0
    cv2_stub.FONT_HERSHEY_SIMPLEX = 0
    cv2_stub.LINE_AA = 0
    sys.modules["cv2"] = cv2_stub

    module_path = Path(__file__).resolve().parents[1] / "webcam.py"
    spec = importlib.util.spec_from_file_location("webcam", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class WebcamCliTests(unittest.TestCase):
    def test_ok_sign_flag_is_parsed(self):
        module = load_webcam_module()

        with patch.object(sys, "argv", ["webcam.py", "--shutdown-on-ok-sign"]):
            args = module.parse_args()

        self.assertTrue(args.shutdown_on_ok_sign)

    def test_middle_finger_pose_does_not_count_as_ok_sign(self):
        module = load_webcam_module()
        landmarks = [types.SimpleNamespace(x=0.5, y=0.5, z=0.0) for _ in range(21)]
        landmarks[12] = types.SimpleNamespace(x=0.5, y=0.2, z=0.0)
        landmarks[10] = types.SimpleNamespace(x=0.5, y=0.4, z=0.0)

        self.assertFalse(module.is_ok_sign_finger_only(landmarks))


if __name__ == "__main__":
    unittest.main()
