
"""Переиспользуемый виджет выбора камеры."""
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QComboBox,
                              QPushButton, QLabel)
from PyQt6.QtCore import QThread, pyqtSignal, Qt

from camera_worker import list_cameras

class ScanThread(QThread):
    done = pyqtSignal(list)
    def run(self):
        cams = list_cameras()
        self.done.emit(cams)

class CameraSelector(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Камера:"))
        self.combo = QComboBox()
        self.combo.setMinimumWidth(200)
        layout.addWidget(self.combo)
        self.btn_refresh = QPushButton("⟳")
        self.btn_refresh.setFixedWidth(30)
        self.btn_refresh.clicked.connect(self.refresh)
        layout.addWidget(self.btn_refresh)
        self._scan = None
        self._cameras = []
        self.refresh()

    def refresh(self):
        self.combo.clear()
        self.combo.addItem("Сканирование...")
        self.btn_refresh.setEnabled(False)
        self._scan = ScanThread()
        self._scan.done.connect(self._on_scan_done)
        self._scan.start()

    def _on_scan_done(self, cameras):
        self.combo.clear()
        self._cameras = cameras
        if not cameras:
            self.combo.addItem("Камеры не найдены")
            self.btn_refresh.setEnabled(True)
            return
        for c in cameras:
            self.combo.addItem(c["label"])
        self.btn_refresh.setEnabled(True)

    def get_camera_index(self):
        idx = self.combo.currentIndex()
        if 0 <= idx < len(self._cameras):
            return self._cameras[idx]["index"], self._cameras[idx].get("backend")
        return 0, None

    def set_enabled(self, enabled):
        self.combo.setEnabled(enabled)
        self.btn_refresh.setEnabled(enabled)
