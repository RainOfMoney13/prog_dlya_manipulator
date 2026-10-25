import cv2
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QImage

try:
    
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("ВНИМАНИЕ: ultralytics не установлен. Работает только цветовая детекция (заглушка).")

class VideoThread(QThread):
    # Сигналы: кадр (numpy), флаг человека (bool), список распознанных классов (list)
    change_pixmap_signal = pyqtSignal(np.ndarray, bool, list)
    
    def __init__(self):
        super().__init__()
        self._run_flag = True
        self.detect_enabled = False
        self.detect_defect = False
        self.classes_to_detect = {"А": False, "Б": False, "В": False}
        self.detect_human = False
        
        # Загружаем модель (если есть)
        if YOLO_AVAILABLE:
            try:
                self.model = YOLO("yolov8n.pt") # Используем стандартную модель
            except Exception as e:
                print(f"Ошибка загрузки YOLO: {e}")
                self.model = None
        else:
            self.model = None

    def run(self):
        # Используем 0 (веб-камера). На конкурсе поменяете на нужный индекс.
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

            # Если включена детекция
            if self.detect_enabled:
                # 1. Детекция человека (по YOLO, если доступно)
                if self.detect_human and self.model:
                    results = self.model(frame, classes=[0], verbose=False) # 0 - класс 'person' в COCO
                    if len(results[0].boxes) > 0:
                        human_detected = True
                        for box in results[0].boxes:
                            x1, y1, x2, y2 = map(int, box.xyxy[0])
                            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                            cv2.putText(frame, "HUMAN", (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

                # 2. Детекция объектов (если человека нет)
                if not human_detected:
                    # Имитация детекции классов А, Б, В (для теста без обученной модели)
                    # В реальности здесь должен быть ваш YOLO, обученный на детали.
                    # Для примера просто ищем цветные пятна:
                    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                    
                    # Красный (Объект А)
                    if self.classes_to_detect["А"]:
                        mask = cv2.inRange(hsv, np.array([0, 100, 100]), np.array([10, 255, 255]))
                        if cv2.countNonZero(mask) > 500:
                            detected_classes.append("А")
                            cv2.putText(frame, "Obj A", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

                    # Зеленый (Объект Б)
                    if self.classes_to_detect["Б"]:
                        mask = cv2.inRange(hsv, np.array([40, 100, 100]), np.array([80, 255, 255]))
                        if cv2.countNonZero(mask) > 500:
                            detected_classes.append("Б")
                            cv2.putText(frame, "Obj B", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

                    # Синий (Объект В)
                    if self.classes_to_detect["В"]:
                        mask = cv2.inRange(hsv, np.array([100, 100, 100]), np.array([130, 255, 255]))
                        if cv2.countNonZero(mask) > 500:
                            detected_classes.append("В")
                            cv2.putText(frame, "Obj V", (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

                    # Брак (желтый)
                    if self.detect_defect:
                        mask = cv2.inRange(hsv, np.array([20, 100, 100]), np.array([40, 255, 255]))
                        if cv2.countNonZero(mask) > 500:
                            detected_classes.append("Брак")
                            cv2.putText(frame, "DEFECT", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

            # Отправляем кадр и данные в главный поток
            self.change_pixmap_signal.emit(frame, human_detected, detected_classes)
            self.msleep(30) # ~30 FPS

        cap.release()

    def stop(self):
        self._run_flag = False
        self.wait()