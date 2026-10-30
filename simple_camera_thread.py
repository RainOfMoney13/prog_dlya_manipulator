import cv2
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal

class SimpleCameraThread(QThread):
    frame_ready = pyqtSignal(np.ndarray)

    def __init__(self, camera_index: int):
        super().__init__()
        self.camera_index = camera_index
        self._run_flag = True

    def run(self):
        # Открываем камеру с указанием драйвера V4L2 (для Linux)
        cap = cv2.VideoCapture(self.camera_index, cv2.CAP_V4L2)
        if not cap.isOpened():
            print(f"Камера {self.camera_index} не найдена.")
            return

        # ВАЖНО: ставим формат MJPG, чтобы не забивать USB-шину
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        while self._run_flag:
            ret, frame = cap.read()
            if not ret or frame is None or frame.size == 0:
                self.msleep(50)
                continue
            self.frame_ready.emit(frame)
            self.msleep(33)

        cap.release()

    def stop(self):
        self._run_flag = False
        self.wait(2000)