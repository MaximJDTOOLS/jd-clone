
"""Игровой режим: скоринг в реальном времени."""
import os
import time
import cv2
import numpy as np
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QMessageBox, QFrame)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap

from dance_data import load_dance, K_TIME, K_POINTS
from pose_tracker import PoseTracker, compute_similarity, draw_skeleton
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

class DancePlayer(QWidget):
    def __init__(self, dance_path):
        super().__init__()
        self.dance = load_dance(dance_path)
        self.dance_path = dance_path
        self.pose = PoseTracker()
        self.cam_worker = None
        self.video_cap = None
        self.playing = False
        self.start_time = 0
        self.total_score = 0
        self.hit_count = 0
        self.total_possible = 0
        self.combo = 0
        self.max_combo = 0
        self._last_frame = None
        self._video_frame = None

        self.setWindowTitle(f"Игра: {self.dance.name}")
        self.resize(1100, 600)
        self.setStyleSheet("""
            QWidget { background: #1a1a2e; color: #eee; }
            QLabel { font-size: 14px; }
            QPushButton { border: none; border-radius: 5px; padding: 10px; font-size: 16px; }
            QPushButton:hover { opacity: 0.85; }
        """)

        layout = QVBoxLayout(self)

        # Верхняя панель
        top = QHBoxLayout()
        top.addWidget(QLabel(f"🎵 {self.dance.name} — {self.dance.artist} [{self.dance.difficulty}]"))
        top.addStretch()
        self.cam_selector = CameraSelector()
        top.addWidget(self.cam_selector)
        self.btn_start = QPushButton("▶ Старт (отсчёт 3 секунды)")
        self.btn_start.setStyleSheet("background: #00c853; color: white;")
        self.btn_start.clicked.connect(self.start_game)
        top.addWidget(self.btn_start)
        self.btn_stop = QPushButton("⏹ Стоп")
        self.btn_stop.setStyleSheet("background: #d50000; color: white;")
        self.btn_stop.clicked.connect(self.stop_game)
        self.btn_stop.setEnabled(False)
        top.addWidget(self.btn_stop)
        layout.addLayout(top)

        # Игровое поле: видео слева, камера справа
        field = QHBoxLayout()

        video_frame = QFrame()
        video_frame.setStyleSheet("background: #000; border: 2px solid #0f3460; border-radius: 5px;")
        vvl = QVBoxLayout(video_frame)
        vvl.setContentsMargins(0, 0, 0, 0)
        self.video_label = QLabel("Видео не выбрано")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setMinimumSize(480, 270)
        self.video_label.setStyleSheet("font-size: 16px; color: #888;")
        vvl.addWidget(self.video_label)
        vl = QLabel("📺 Эталонное видео")
        vl.setStyleSheet("color: #00e5ff; font-size: 14px; font-weight: bold; padding: 5px;")
        vl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vvl.addWidget(vl)
        field.addWidget(video_frame)

        cam_frame = QFrame()
        cam_frame.setStyleSheet("background: #000; border: 2px solid #0f3460; border-radius: 5px;")
        cvl = QVBoxLayout(cam_frame)
        cvl.setContentsMargins(0, 0, 0, 0)
        self.cam_label = QLabel("Камера не запущена")
        self.cam_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cam_label.setMinimumSize(480, 270)
        self.cam_label.setStyleSheet("font-size: 16px; color: #888;")
        cvl.addWidget(self.cam_label)
        self.countdown = CountdownOverlay(self.cam_label)
        cl = QLabel("📷 Ваша камера")
        cl.setStyleSheet("color: #ff6d00; font-size: 14px; font-weight: bold; padding: 5px;")
        cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cvl.addWidget(cl)
        field.addWidget(cam_frame)

        layout.addLayout(field, stretch=1)

        # Панель счёта
        score_bar = QHBoxLayout()
        self.score_label = QLabel("Очки: 0")
        self.score_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #00e5ff;")
        score_bar.addWidget(self.score_label)

        self.combo_label = QLabel("Комбо: 0")
        self.combo_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #ff6d00;")
        score_bar.addWidget(self.combo_label)

        self.acc_label = QLabel("Точность: 0%")
        self.acc_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #00c853;")
        score_bar.addWidget(self.acc_label)

        self.feedback_label = QLabel("")
        self.feedback_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #fff;")
        self.feedback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_bar.addWidget(self.feedback_label)

        layout.addLayout(score_bar)

        # Таймер игрового цикла
        self._timer = QTimer()
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._game_tick)

    def start_game(self):
        idx, backend = self.cam_selector.get_camera_index()

        # Запуск камеры
        self.cam_worker = CameraWorker(idx, backend, draw_skeleton=True)
        self.cam_worker.set_pose_tracker(self.pose)
        self.cam_worker.frame_ready.connect(self.on_cam_frame)
        self.cam_worker.error.connect(self.on_cam_error)
        self.cam_worker.start()

        # Запуск видео
        if self.dance.video_path and os.path.exists(self.dance.video_path):
            self.video_cap = cv2.VideoCapture(self.dance.video_path)

        self.cam_selector.set_enabled(False)
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)

        # Отсчёт
        self.countdown.start(self._begin_play)

    def _begin_play(self):
        self.playing = True
        self.start_time = time.time()
        self.total_score = 0
        self.hit_count = 0
        self.total_possible = 0
        self.combo = 0
        self.max_combo = 0
        self._timer.start()

    def on_cam_error(self, msg):
        QMessageBox.warning(self, "Ошибка камеры", msg)
        self.stop_game()

    def on_cam_frame(self, frame):
        self._last_frame = frame
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
        self.cam_label.setPixmap(QPixmap.fromImage(qimg).scaled(
            self.cam_label.width(), self.cam_label.height(),
            Qt.AspectRatioMode.KeepAspectRatio))

    def _game_tick(self):
        if not self.playing:
            return

        elapsed = time.time() - self.start_time

        # Показ видео
        if self.video_cap:
            ret, vframe = self.video_cap.read()
            if ret and vframe is not None:
                h, w = vframe.shape[:2]
                rgb = cv2.cvtColor(vframe, cv2.COLOR_BGR2RGB)
                qimg = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
                self.video_label.setPixmap(QPixmap.fromImage(qimg).scaled(
                    self.video_label.width(), self.video_label.height(),
                    Qt.AspectRatioMode.KeepAspectRatio))

        # Найти ближайшую целевую позу
        best_pose = None
        best_diff = float("inf")
        for p in self.dance.poses:
            diff = abs(p[K_TIME] - elapsed)
            if diff < best_diff:
                best_diff = diff
                best_pose = p

        if best_pose and best_diff < 1.0 and self._last_frame is not None:
            rgb = cv2.cvtColor(self._last_frame, cv2.COLOR_BGR2RGB)
            landmarks = self.pose.process(rgb)
            if landmarks:
                score = compute_similarity(landmarks, best_pose[K_POINTS])
                self.total_possible += 1
                if score > 0.75:
                    self.hit_count += 1
                    self.combo += 1
                    self.max_combo = max(self.combo, self.max_combo)
                    self.total_score += int(score * 100) + self.combo * 5
                    self.feedback_label.setText("✅ Отлично!")
                    self.feedback_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #00c853;")
                elif score > 0.55:
                    self.combo += 1
                    self.max_combo = max(self.combo, self.max_combo)
                    self.total_score += int(score * 50)
                    self.feedback_label.setText("🟡 Норм")
                    self.feedback_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #ffc107;")
                else:
                    self.combo = 0
                    self.feedback_label.setText("❌ Мимо")
                    self.feedback_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #d50000;")

        self.score_label.setText(f"Очки: {self.total_score}")
        self.combo_label.setText(f"Комбо: {self.combo}")
        acc = (self.hit_count / max(1, self.total_possible)) * 100
        self.acc_label.setText(f"Точность: {acc:.0f}%")

        # Конец танца
        total_duration = self.dance.poses[-1][K_TIME] if self.dance.poses else 1
        if elapsed > total_duration + 2:
            self._finish_game()

    def _finish_game(self):
        self.playing = False
        self._timer.stop()

        if self.cam_worker:
            self.cam_worker.stop()
            self.cam_worker = None
        if self.video_cap:
            self.video_cap.release()
            self.video_cap = None

        acc = (self.hit_count / max(1, self.total_possible)) * 100
        if acc >= 90:
            grade = "S"
        elif acc >= 75:
            grade = "A"
        elif acc >= 60:
            grade = "B"
        elif acc >= 40:
            grade = "C"
        else:
            grade = "D"

        msg = (f"🎉 Танец завершён!\n\n"
               f"Очки: {self.total_score}\n"
               f"Точность: {acc:.0f}%\n"
               f"Макс. комбо: {self.max_combo}\n"
               f"Оценка: {grade}")
        QMessageBox.information(self, "Результат", msg)

        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.cam_selector.set_enabled(True)
        self.feedback_label.setText("")

    def stop_game(self):
        self.playing = False
        self._timer.stop()
        if self.cam_worker:
            self.cam_worker.stop()
            self.cam_worker = None
        if self.video_cap:
            self.video_cap.release()
            self.video_cap = None
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.cam_selector.set_enabled(True)
        self.feedback_label.setText("")

    def closeEvent(self, event):
        self.stop_game()
        self.pose.close()
        event.accept()
