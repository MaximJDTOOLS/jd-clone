"""Виджет отсчёта 3-2-1 поверх видео."""
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QLabel

class CountdownOverlay(QLabel):
    """Полупрозрачная цифра поверх видео."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 160px;
                font-weight: bold;
                background: rgba(0,0,0,120);
                border-radius: 20px;
            }
        """)
        self.hide()
        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)
        self._count = 0
        self._callback = None

    def start(self, callback=None):
        """Запускает отсчёт 3-2-1, затем вызывает callback."""
        self._callback = callback
        self._count = 3
        self.setText(str(self._count))
        self.adjustSize()
        self._center()
        self.show()
        self.raise_()
        self._timer.start(1000)

    def _tick(self):
        self._count -= 1
        if self._count > 0:
            self.setText(str(self._count))
            self.adjustSize()
            self._center()
            self.raise_()
        else:
            self._timer.stop()
            self.hide()
            if self._callback:
                self._callback()

    def _center(self):
        if self.parent():
            pw = self.parent().width()
            ph = self.parent().height()
            self.move((pw - self.width()) // 2, (ph - self.height()) // 2)

    def stop(self):
        self._timer.stop()
        self.hide()
