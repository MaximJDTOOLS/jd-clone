
"""Редактор танцев: запись поз с камеры, выбор аудио/видео."""
import os
import time
import cv2
import numpy as np
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QComboBox, QFileDialog, QGroupBox, QMessageBox)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QFont

from dance_data import Dance, save_dance, K_TIME, K_POINTS, DANCES_DIR
from pose_tracker import PoseTracker
from camera_worker import CameraWorker
from camera_selector import CameraSelector

class CountdownOverlay(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("font-size: 120px; font-weight: bold; color: #00e5ff; background: rgba(0,0,0,120);")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hide()

    def start(self, callback):
        self._callback = callback
        self._count = 3
        self._show_num()
        QTimer.singleShot(1000, self._tick)

    def _tick(self):
        self._count -= 1
        if self._count > 0:
            self._show_num()
            QTimer.singleShot(1000, self._tick)
        else:
            self.hide()
            self._callback()

    def _show_num(self):
        self.setText(str(self._count))
        self.show()
        self.raise_()

class DanceEditor(QWidget):
    closed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Редактор танцев")
        self.resize(900, 650)
        self.setStyleSheet("""
            QWidget { background: #1a1a2e; color: #eee; }
            QGroupBox { border: 1px solid #0f3460; border-radius: 5px; margin-top: 10px; padding-top: 15px; font-weight: bold; }
            QGroupBox::title { left: 10px; padding: 0 5px; }
            QLineEdit, QComboBox { background: #16213e; border: 1px solid #0f3460; padding: 5px; border-radius: 3px; }
            QPushButton { border: none; border-radius: 5px; padding: 8px; font-size: 14px; }
            QPushButton:hover { opacity: 0.85; }
        """)

        self.dance = Dance()
        self.pose = PoseTracker()
        self.cam_worker = None
        self.recording = False
        self.record_start = 0
        self.video_cap = None

        layout = QVBoxLayout(self)

        # Группа метаданных
        meta_group = QGroupBox("Информация о танце")
        meta_layout = QHBoxLayout(meta_group)
        meta_layout.addWidget(QLabel("Название:"))
        self.name_edit = QLineEdit()
        meta_layout.addWidget(self.name_edit)
        meta_layout.addWidget(QLabel("Исполнитель:"))
        self.artist_edit = QLineEdit()
        meta_layout.addWidget(self.artist_edit)
        meta_layout.addWidget(QLabel("Сложность:"))
        self.diff_combo = QComboBox()
        self.diff_combo.addItems(["Easy", "Medium", "Hard", "Extreme"])
        meta_layout.addWidget(self.diff_combo)
        meta_layout.addWidget(QLabel("BPM:"))
        self.bpm_edit = QLineEdit("120")
        self.bpm_edit.setFixedWidth(50)
        meta_layout.addWidget(self.bpm_edit)
        layout.addWidget(meta_group)

        # Группа медиа
        media_group = QGroupBox("Медиа файлы")
        media_layout = QHBoxLayout(media_group)
        media_layout.addWidget(QLabel("Аудио:"))
        self.audio_label = QLabel("не выбрано")
        self.audio_label.setStyleSheet("color: #888;")
        media_layout.addWidget(self.audio_label)
        btn_audio = QPushButton("📁 Выбрать")
        btn_audio.setStyleSheet("background: #1565c0; color: white;")
        btn_audio.clicked.connect(self.select_audio)
        media_layout.addWidget(btn_audio)
        media_layout.addWidget(QLabel("Видео:"))
        self.video_label = QLabel("не выбрано")
        self.video_label.setStyleSheet("color: #888;")
        media_layout.addWidget(self.video_label)
        btn_video = QPushButton("📁 Выбрать")
        btn_video.setStyleSheet("background: #1565c0; color: white;")
        btn_video.clicked.connect(self.select_video)
        media_layout.addWidget(btn_video)
        layout.addWidget(media_group)

        # Группа камеры
        cam_group = QGroupBox("Камера")
        cam_layout = QHBoxLayout(cam_group)
        self.cam_selector = CameraSelector()
        cam_layout.addWidget(self.cam_selector)
        self.btn_cam_start = QPushButton("▶ Запустить камеру")
        self.btn_cam_start.setStyleSheet("background: #00c853; color: white;")
        self.btn_cam_start.clicked.connect(self.toggle_camera)
        cam_layout.addWidget(self.btn_cam_start)
        layout.addWidget(cam_group)

        # Превью камеры
        self.preview_label = QLabel("Камера не запущена")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(640, 360)
        self.preview_label.setStyleSheet("background: #000; border: 2px solid #0f3460; border-radius: 5px; font-size: 18px; color: #888;")
        layout.addWidget(self.preview_label)

        # Оверлей отсчёта
        self.countdown = CountdownOverlay(self.preview_label)

        # Кнопки записи
        btn_layout = QHBoxLayout()
        self.btn_record = QPushButton("⏺ Начать запись")
        self.btn_record.setStyleSheet("background: #d50000; color: white; font-size: 18px; padding: 12px;")
        self.btn_record.clicked.connect(self.start_recording)
        self.btn_record.setEnabled(False)
        btn_layout.addWidget(self.btn_record)

        self.btn_stop = QPushButton("⏹ Остановить")
        self.btn_stop.setStyleSheet("background: #ff8f00; color: white; font-size: 18px; padding: 12px;")
        self.btn_stop.clicked.connect(self.stop_recording)
        self.btn_stop.setEnabled(False)
        btn_layout.addWidget(self.btn_stop)

        self.btn_save = QPushButton("💾 Сохранить танец")
        self.btn_save.setStyleSheet("background: #00c853; color: white; font-size: 18px; padding: 12px;")
        self.btn_save.clicked.connect(self.save)
        btn_layout.addWidget(self.btn_save)
        layout.addLayout(btn_layout)

        # Статус
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #00e5ff; font-size: 13px;")
        layout.addWidget(self.status_label)

        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self.update_frame)

    def select_audio(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выбрать аудио", "", "Audio (*.mp3 *.wav *.ogg *.m4a)")
        if path:
            self.dance.audio_path = path
            self.audio_label.setText(os.path.basename(path))
            self.audio_label.setStyleSheet("color: #00e5ff;")

    def select_video(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выбрать видео", "", "Video (*.mp4 *.avi *.mov *.mkv)")
        if path:
            self.dance.video_path = path
            self.video_label.setText(os.path.basename(path))
            self.video_label.setStyleSheet("color: #00e5ff;")

    def toggle_camera(self):
        if self.cam_worker and self.cam_worker.isRunning():
            self.cam_worker.stop()
            self.cam_worker = None
            self.btn_cam_start.setText("▶ Запустить камеру")
            self.btn_cam_start.setStyleSheet("background: #00c853; color: white;")
            self.btn_record.setEnabled(False)
            self.cam_selector.set_enabled(True)
            self.preview_label.setText("Камера остановлена")
            self.preview_label.setPixmap(QPixmap())
            return

        idx, backend = self.cam_selector.get_camera_index()
        self.cam_worker = CameraWorker(idx, backend, draw_skeleton=True)
        self.cam_worker.set_pose_tracker(self.pose)
        self.cam_worker.frame_ready.connect(self.on_frame)
        self.cam_worker.error.connect(self.on_cam_error)
        self.cam_worker.start()
        self.btn_cam_start.setText("⏹ Остановить камеру")
        self.btn_cam_start.setStyleSheet("background: #d50000; color: white;")
        self.btn_record.setEnabled(True)
        self.cam_selector.set_enabled(False)

    def on_cam_error(self, msg):
        QMessageBox.warning(self, "Ошибка камеры", msg)
        self.cam_worker = None
        self.btn_cam_start.setText("▶ Запустить камеру")
        self.btn_cam_start.setStyleSheet("background: #00c853; color: white;")
        self.btn_record.setEnabled(False)
        self.cam_selector.set_enabled(True)

    def on_frame(self, frame):
        self._last_frame = frame
        if self.recording:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            landmarks = self.pose.process(rgb)
            t = time.time() - self.record_start
            if landmarks:
                self.dance.add_pose(t, landmarks)

    def update_frame(self):
        pass

    def start_recording(self):
        if not self.cam_worker or not self.cam_worker.isRunning():
            QMessageBox.warning(self, "Внимание", "Сначала запустите камеру!")
            return
        self.btn_record.setEnabled(False)
        self.btn_cam_start.setEnabled(False)
        self.countdown.start(self._do_record)

    def _do_record(self):
        self.recording = True
        self.record_start = time.time()
        self.dance.poses = []
        self.btn_stop.setEnabled(True)
        self.btn_cam_start.setEnabled(True)
        self.status_label.setText(f"Запись... поз: {len(self.dance.poses)}")
        self._status_timer = QTimer()
        self._status_timer.timeout.connect(self._update_status)
        self._status_timer.start(200)

    def _update_status(self):
        if self.recording:
            self.status_label.setText(f"Запись... поз: {len(self.dance.poses)} | время: {time.time() - self.record_start:.1f}с")

    def stop_recording(self):
        self.recording = False
        self.btn_stop.setEnabled(False)
        self.btn_record.setEnabled(True)
        try:
            self._status_timer.stop()
        except Exception:
            pass
        self.status_label.setText(f"Записано поз: {len(self.dance.poses)}")

    def save(self):
        self.dance.name = self.name_edit.text() or "Без названия"
        self.dance.artist = self.artist_edit.text() or "Unknown"
        self.dance.difficulty = self.diff_combo.currentText()
        try:
            self.dance.bpm = int(self.bpm_edit.text() or 120)
        except ValueError:
            self.dance.bpm = 120

        if not self.dance.poses:
            QMessageBox.warning(self, "Внимание", "Нет записанных поз! Сначала запишите танец.")
            return

        if not os.path.exists(DANCES_DIR):
            os.makedirs(DANCES_DIR)
        path = os.path.join(DANCES_DIR, f"{self.dance.name}.dance")
        save_dance(self.dance, path)
        QMessageBox.information(self, "Готово", f"Танец сохранён: {path}\nПоз: {len(self.dance.poses)}")
        self.name_edit.setText("")

    def closeEvent(self, event):
        if self.cam_worker:
            self.cam_worker.stop()
        if self.video_cap:
            self.video_cap.release()
        self.pose.close()
        self.closed.emit()
        event.accept()
