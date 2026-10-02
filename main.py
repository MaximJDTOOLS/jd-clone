
"""Главное меню игры."""
import os
import sys
import glob
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QListWidget, QLabel, QFileDialog, QMessageBox,
    QInputDialog)
from PyQt6.QtCore import Qt

from dance_data import load_dance, save_dance

DANCES_DIR = "dances"

def ensure_dir():
    if not os.path.exists(DANCES_DIR):
        os.makedirs(DANCES_DIR)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Just Dance Clone — MediaPipe")
        self.resize(700, 500)
        self.setStyleSheet(self._style())
        ensure_dir()

        self._editor = None
        self._player = None

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        title = QLabel("🎵 Just Dance Clone")
        title.setStyleSheet("font-size: 28px; font-weight: bold; color: #00e5ff; padding: 10px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Трекинг поз через MediaPipe • Редактор танцев • Скоринг")
        subtitle.setStyleSheet("font-size: 13px; color: #aaa;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("font-size: 14px; padding: 5px;")
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()

        btn_play = QPushButton("▶ Играть")
        btn_play.setStyleSheet("background: #00c853; color: white; font-size: 16px; padding: 10px;")
        btn_play.clicked.connect(self.play_dance)
        btn_layout.addWidget(btn_play)

        btn_editor = QPushButton("✏ Редактор танцев")
        btn_editor.setStyleSheet("background: #ff6d00; color: white; font-size: 16px; padding: 10px;")
        btn_editor.clicked.connect(self.open_editor)
        btn_layout.addWidget(btn_editor)

        btn_import = QPushButton("📥 Импорт")
        btn_import.setStyleSheet("background: #651fff; color: white; font-size: 16px; padding: 10px;")
        btn_import.clicked.connect(self.import_dance)
        btn_layout.addWidget(btn_import)

        btn_delete = QPushButton("🗑 Удалить")
        btn_delete.setStyleSheet("background: #d50000; color: white; font-size: 16px; padding: 10px;")
        btn_delete.clicked.connect(self.delete_dance)
        btn_layout.addWidget(btn_delete)

        layout.addLayout(btn_layout)

        self.refresh_list()

    def _style(self):
        return """
            QMainWindow { background: #1a1a2e; }
            QWidget { color: #eee; }
            QListWidget { background: #16213e; border: 1px solid #0f3460; border-radius: 5px; }
            QListWidget::item:selected { background: #0f3460; color: #00e5ff; }
            QPushButton { border: none; border-radius: 5px; }
            QPushButton:hover { opacity: 0.85; }
        """

    def refresh_list(self):
        self.list_widget.clear()
        files = sorted(glob.glob(os.path.join(DANCES_DIR, "*.dance")))
        for f in files:
            name = os.path.splitext(os.path.basename(f))[0]
            try:
                d = load_dance(f)
                label = f"{d.name} — {d.artist} [{d.difficulty}]"
            except Exception:
                label = f"{name} (ошибка загрузки)"
            self.list_widget.addItem(label)
        if not self.list_widget.count():
            self.list_widget.addItem("Нет танцев. Создайте в редакторе.")

    def get_selected_path(self):
        row = self.list_widget.currentRow()
        files = sorted(glob.glob(os.path.join(DANCES_DIR, "*.dance")))
        if 0 <= row < len(files):
            return files[row]
        return None

    def play_dance(self):
        path = self.get_selected_path()
        if not path:
            QMessageBox.information(self, "Инфо", "Выберите танец из списка")
            return
        from dance_player import DancePlayer
        self._player = DancePlayer(path)
        self._player.show()

    def open_editor(self):
        from dance_editor import DanceEditor
        self._editor = DanceEditor()
        self._editor.closed.connect(self.refresh_list)
        self._editor.show()

    def import_dance(self):
        path, _ = QFileDialog.getOpenFileName(self, "Импорт танца", "", "Dance files (*.dance)")
        if path:
            try:
                d = load_dance(path)
                name = d.name or os.path.splitext(os.path.basename(path))[0]
                dest = os.path.join(DANCES_DIR, f"{name}.dance")
                save_dance(d, dest)
                self.refresh_list()
                QMessageBox.information(self, "Готово", f"Танец импортирован: {name}")
            except Exception as e:
                QMessageBox.warning(self, "Ошибка", f"Не удалось импортировать: {e}")

    def delete_dance(self):
        path = self.get_selected_path()
        if not path:
            QMessageBox.information(self, "Инфо", "Выберите танец для удаления")
            return
        reply = QMessageBox.question(self, "Удаление", f"Удалить {os.path.basename(path)}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            os.remove(path)
            self.refresh_list()

def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
