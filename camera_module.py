import cv2
import numpy as np
from PyQt5.QtCore import pyqtSignal, QThread
from PyQt5.QtGui import QImage
from color_defect_detector import ColorDefectDetector

class CameraThread(QThread):
    frame_signal = pyqtSignal(int, np.ndarray, list)
    
    def __init__(self, camera_id=0, process_vision=False):
        super().__init__()
        self.camera_id = camera_id
        self.process_vision = process_vision
        self.running = False
        self.detector = ColorDefectDetector()
        
    def run(self):
        self.running = True
        cap = cv2.VideoCapture(self.camera_id)
        
        if not cap.isOpened():
            print(f"Ошибка: Камера {self.camera_id} не найдена")
            return
            
        while self.running:
            ret, frame = cap.read()
            if ret:
                defects = []
                if self.process_vision:
                    defects = self.detector.detect_color_defects(frame)
                    frame = self.detector.draw_defects(frame, defects)
                
                self.frame_signal.emit(self.camera_id, frame, defects)
            self.msleep(30)
            
        cap.release()

    def stop(self):
        self.running = False
        self.wait()