
"""MediaPipe Pose обёртка + скоринг."""
import numpy as np

try:
    import mediapipe as mp
    HAS_MP = True
    try:
        _ = mp.solutions.pose
        MP_API = "solutions"
    except Exception:
        try:
            from mediapipe.tasks.python.vision import PoseLandmarker
            MP_API = "tasks"
        except Exception:
            MP_API = "none"
except ImportError:
    HAS_MP = False
    MP_API = "none"

POSE_CONNECTIONS = [
    (11,12),(11,13),(13,15),(12,14),(14,16),
    (11,23),(12,24),(23,24),(23,25),(24,26),
    (25,27),(27,29),(29,31),(26,28),(28,30),(30,32),
]

SCORE_INDICES = [11,12,13,14,15,16,23,24,25,26,27,28]

class PoseTracker:
    def __init__(self):
        self.pose = None
        self._init_pose()

    def _init_pose(self):
        if not HAS_MP:
            return
        try:
            if MP_API == "solutions":
                self.pose = mp.solutions.pose.Pose(
                    static_image_mode=False,
                    model_complexity=1,
                    smooth_landmarks=True,
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
            else:
                self.pose = None
        except Exception as e:
            print(f"PoseTracker init error: {e}")
            self.pose = None

    def process(self, frame_rgb):
        if self.pose is None:
            return None
        try:
            result = self.pose.process(frame_rgb)
            if result and result.pose_landmarks:
                return result.pose_landmarks.landmark
        except Exception as e:
            print(f"PoseTracker process error: {e}")
        return None

    def close(self):
        if self.pose:
            try:
                self.pose.close()
            except Exception:
                pass
            self.pose = None

def get_landmark_array(landmarks):
    arr = np.zeros((33, 3), dtype=np.float32)
    for i in range(min(33, len(landmarks))):
        lm = landmarks[i]
        arr[i] = [lm.x, lm.y, lm.z if hasattr(lm, "z") else 0.0]
    return arr

def compute_similarity(pose_a, pose_b):
    """Косинусное сходство по ключевым точкам."""
    if pose_a is None or pose_b is None:
        return 0.0
    try:
        a = get_landmark_array(pose_a)
        if isinstance(pose_b, dict):
            b = np.zeros((33, 3), dtype=np.float32)
            for k, v in pose_b.items():
                idx = int(k)
                if idx < 33:
                    b[idx] = [v.get("x", 0), v.get("y", 0), v.get("z", 0)]
        else:
            b = get_landmark_array(pose_b)

        va = a[SCORE_INDICES].flatten()
        vb = b[SCORE_INDICES].flatten()
        na = np.linalg.norm(va)
        nb = np.linalg.norm(vb)
        if na < 1e-6 or nb < 1e-6:
            return 0.0
        sim = float(np.dot(va, vb) / (na * nb))
        return max(0.0, min(1.0, sim))
    except Exception:
        return 0.0

def draw_skeleton(frame, landmarks, color=(0,255,0), thickness=2):
    """Рисует скелет на кадре."""
    import cv2
    if landmarks is None:
        return frame
    h, w = frame.shape[:2]
    pts = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks]
    for a, b in POSE_CONNECTIONS:
        if a < len(pts) and b < len(pts):
            cv2.line(frame, pts[a], pts[b], color, thickness)
    for p in pts:
        cv2.circle(frame, p, 3, color, -1)
    return frame
