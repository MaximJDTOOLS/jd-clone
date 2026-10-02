
"""Поток камеры с поддержкой DroidCam и виртуальных камер."""
import cv2
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

BACKENDS = [
    ("DShow", cv2.CAP_DSHOW),
    ("MSMF", cv2.CAP_MSMF),
    ("ANY",  cv2.CAP_ANY),
]

def list_cameras(max_index=20):
    """Сканирует индексы 0..max_index с разными бэкендами."""
    cameras = []
    for idx in range(max_index + 1):
        found = False
        for bname, backend in BACKENDS:
            try:
                cap = cv2.VideoCapture(idx, backend)
                if not cap.isOpened():
                    cap.release()
                    continue
                # Несколько попыток чтения (DroidCam медленный)
                ret = False
                for _ in range(15):
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        break
                cap.release()
                if ret:
                    cameras.append({"index": idx, "backend": bname, "label": f"Камера {idx} ({bname})"})
                    found = True
                    break
            except Exception:
                try:
                    cap.release()
                except Exception:
                    pass
        if not found:
            # Пробуем без бэкенда
            try:
                cap = cv2.VideoCapture(idx)
                ret, frame = cap.read()
                cap.release()
                if ret and frame is not None:
                    cameras.append({"index": idx, "backend": "DEF", "label": f"Камера {idx}"})
            except Exception:
                pass
    return cameras

class CameraWorker(QThread):
    frame_ready = pyqtSignal(np.ndarray)
    error = pyqtSignal(str)

    def __init__(self, camera_index=0, backend_name=None, draw_skeleton=True):
        super().__init__()
        self.camera_index = camera_index
        self.backend_name = backend_name
        self.draw_skeleton = draw_skeleton
        self._running = False
        self._pose = None

    def set_pose_tracker(self, pose):
        self._pose = pose

    def run(self):
        self._running = True
        backend = cv2.CAP_ANY
        for bname, bval in BACKENDS:
            if bname == self.backend_name:
                backend = bval
                break

        cap = cv2.VideoCapture(self.camera_index, backend)
        if not cap.isOpened():
            cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            self.error.emit(f"Не удалось открыть камеру {self.camera_index}")
            return

        # Прогрев
        for _ in range(5):
            cap.read()

        while self._running:
            ret, frame = cap.read()
            if not ret or frame is None:
                # Попытка переподключения
                cap.release()
                cap = cv2.VideoCapture(self.camera_index, backend)
                if not cap.isOpened():
                    self.error.emit(f"Камера {self.camera_index} отключилась")
                    return
                continue

            frame = cv2.flip(frame, 1)

            if self._pose and self.draw_skeleton:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                landmarks = self._pose.process(rgb)
                if landmarks:
                    from pose_tracker import draw_skeleton
                    frame = draw_skeleton(frame, landmarks)

            self.frame_ready.emit(frame.copy())

        cap.release()

    def stop(self):
        self._running = False
        self.wait(3000)
