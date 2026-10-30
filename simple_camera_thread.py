import cv2
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal


class SimpleCameraThread(QThread):
    """Простой поток вывода видео без какой-либо детекции."""

    frame_ready = pyqtSignal(np.ndarray)

    def __init__(self, camera_index: int):
        super().__init__()
        self.camera_index = camera_index
        self._run_flag = True

    def run(self):
        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            # Камера недоступна (например, на ноутбуке) — тихо выходим.
            print(f"Камера {self.camera_index} не найдена — поток не запущен.")
            return

        while self._run_flag:
            ret, frame = cap.read()
            if not ret:
                # Кадр не пришёл — не роняем поток, просто ждём.
                self.msleep(50)
                continue
            self.frame_ready.emit(frame)
            self.msleep(33)  # ~30 FPS

        cap.release()

    def stop(self):
        self._run_flag = False
        self.wait(2000)