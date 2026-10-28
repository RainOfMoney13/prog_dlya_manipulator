import cv2
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QImage
from ultralytics import YOLO

class VideoThread(QThread):
    change_pixmap_signal = pyqtSignal(np.ndarray, bool, list)
    
    def __init__(self):
        super().__init__()
        self._run_flag = True
        self.detect_enabled = False
        self.detect_defect = False
        self.classes_to_detect = {"А": False, "Б": False, "В": False}
        self.detect_human = False
        
        try:
            # 1. Модель для ваших деталей (обученная)
            self.model = YOLO("runs/train/defect_model/weights/best.pt") 
            # 2. Модель для поиска людей (стандартная)
            self.human_model = YOLO("yolov8n.pt")
            print("Модели YOLO успешно загружены!")
        except Exception as e:
            print(f"Ошибка загрузки YOLO: {e}")
            self.model = None
            self.human_model = None

    def run(self):
        cap = cv2.VideoCapture(0) 
        
        if not cap.isOpened():
            print("Камера не найдена!")
            return

        while self._run_flag:
            ret, frame = cap.read()
            if not ret:
                continue
                
            human_detected = False
            detected_classes = []

            if self.detect_enabled:
                # === 1. ДЕТЕКЦИЯ ЧЕЛОВЕКА (стандартная модель) ===
                if self.detect_human and self.human_model:
                    human_results = self.human_model(frame, classes=[0], verbose=False) # 0 - person
                    if len(human_results[0].boxes) > 0:
                        human_detected = True
                        for box in human_results[0].boxes:
                            x1, y1, x2, y2 = map(int, box.xyxy[0])
                            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                            cv2.putText(frame, "HUMAN", (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

                # === 2. ДЕТЕКЦИЯ ДЕТАЛЕЙ (обученная модель) ===
                # Если человека нет, ищем детали
                if not human_detected and self.model:
                    results = self.model(frame, conf=0.5, verbose=False)
                    
                    for r in results:
                        for box in r.boxes:
                            cls_id = int(box.cls[0])
                            conf = float(box.conf[0])
                            
                            # Получаем имя класса из модели
                            class_name = self.model.names[cls_id]
                            
                            # Сопоставляем английское имя (из модели) с русским (для логов)
                            name_map = {"object_A": "А", "object_B": "Б", "object_V": "В", "defect": "Брак"}
                            ru_name = name_map.get(class_name, class_name)
                            
                            # Проверяем, включен ли этот класс в чекбоксах
                            if ru_name in ["А", "Б", "В"] and not self.classes_to_detect.get(ru_name, False):
                                continue
                            if ru_name == "Брак" and not self.detect_defect:
                                continue
                            
                            # Рисуем рамку и текст
                            x1, y1, x2, y2 = map(int, box.xyxy[0])
                            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                            label = f"{ru_name} ({conf:.2f})"
                            cv2.putText(frame, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                            
                            detected_classes.append(ru_name)

            # Отправляем кадр и данные в главный поток
            self.change_pixmap_signal.emit(frame, human_detected, detected_classes)
            self.msleep(30) # ~30 FPS

        cap.release()

    def stop(self):
        self._run_flag = False
        self.wait()