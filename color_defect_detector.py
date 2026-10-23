import cv2
import numpy as np

class ColorDefectDetector:
    def __init__(self):
        self.defect_colors_hsv = {
            'Красный': ([0, 100, 100], [10, 255, 255]),
            'Желтый': ([20, 100, 100], [40, 255, 255]),
            'Зеленый': ([40, 100, 100], [80, 255, 255]),
            'Синий': ([100, 100, 100], [130, 255, 255]),
        }
        self.display_colors = {
            'Красный': (0, 0, 255), 'Синий': (255, 0, 0),
            'Зеленый': (0, 255, 0), 'Желтый': (0, 255, 255)
        }
        self.reset_statistics()

    def detect_color_defects(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        detected = []
        
        for color_name, (lower, upper) in self.defect_colors_hsv.items():
            mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5,5), np.uint8))
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if 100 < area < 5000:
                    x, y, w, h = cv2.boundingRect(cnt)
                    detected.append({'color': color_name, 'bbox': [x, y, w, h], 'area': area})
                    
                    # Обновление статистики
                    if color_name == 'Красный': self.red += 1
                    elif color_name == 'Синий': self.blue += 1
                    elif color_name == 'Зеленый': self.green += 1
                    elif color_name == 'Желтый': self.yellow += 1
        
        self.total += len(detected)
        return detected

    def draw_defects(self, frame, defects):
        for d in defects:
            x, y, w, h = d['bbox']
            color = self.display_colors.get(d['color'], (255,255,255))
            cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
            cv2.putText(frame, f"{d['color']}", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        return frame

    def reset_statistics(self):
        self.total = 0
        self.red = 0
        self.blue = 0
        self.green = 0
        self.yellow = 0