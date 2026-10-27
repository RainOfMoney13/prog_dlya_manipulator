import os
import cv2
import numpy as np
import yaml

class AutoLabeler:
    def __init__(self, input_path="database", output_path="labeled_dataset"):
        self.input_path = input_path
        self.output_path = output_path
        self.classes = ["object_A", "object_B", "object_V", "defect"] # Имена классов (можно поменять)
        
        # Создаем папки для YOLO
        for folder in ["images/train", "images/val", "labels/train", "labels/val"]:
            os.makedirs(os.path.join(self.output_path, folder), exist_ok=True)

    def detect_objects(self, image):
        """Автоматическое обнаружение объектов (по контрасту/контурам)"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        # Блюр для сглаживания шумов
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        # Поиск краев
        edges = cv2.Canny(blurred, 50, 150)
        
        # Морфологические операции (чтобы контуры были целыми)
        kernel = np.ones((5,5), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=1)
        
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        bboxes = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if 500 < area < 50000: # Фильтр по площади
                x, y, w, h = cv2.boundingRect(cnt)
                bboxes.append([x, y, w, h])
        return bboxes

    def process_dataset(self):
        print("Начинаем авторазметку...")
        image_files = [f for f in os.listdir(self.input_path) if f.endswith(('.jpg', '.png', '.jpeg'))]
        
        if not image_files:
            print(f"ОШИБКА: В папке {self.input_path} нет картинок!")
            return

        # Разделяем на train (80%) и val (20%)
        split_idx = int(len(image_files) * 0.8)
        
        for idx, filename in enumerate(image_files):
            img_path = os.path.join(self.input_path, filename)
            image = cv2.imread(img_path)
            if image is None: continue
            
            h_img, w_img = image.shape[:2]
            split = "train" if idx < split_idx else "val"
            
            # 1. Сохраняем картинку
            out_img_path = os.path.join(self.output_path, "images", split, filename)
            cv2.imwrite(out_img_path, image)
            
            # 2. Ищем объекты и пишем txt-файл
            bboxes = self.detect_objects(image)
            label_name = os.path.splitext(filename)[0] + ".txt"
            label_path = os.path.join(self.output_path, "labels", split, label_name)
            
            with open(label_path, 'w') as f:
                for bbox in bboxes:
                    x, y, w, h = bbox
                    # Конвертация в формат YOLO (от 0 до 1)
                    x_center = (x + w/2) / w_img
                    y_center = (y + h/2) / h_img
                    w_norm = w / w_img
                    h_norm = h / h_img
                    # Класс 0 (пока ставим всем объектам класс 0, потом можно переразметить)
                    f.write(f"0 {x_center:.6f} {y_center:.6f} {w_norm:.6f} {h_norm:.6f}\n")
            
            if idx % 10 == 0:
                print(f"Обработано {idx}/{len(image_files)}")

        # 3. Создаем файл конфигурации для YOLO
        config = {
            'path': os.path.abspath(self.output_path),
            'train': 'images/train',
            'val': 'images/val',
            'names': {i: name for i, name in enumerate(self.classes)}
        }
        with open(os.path.join(self.output_path, "dataset.yaml"), 'w') as f:
            yaml.dump(config, f)

        print(f"ГОТОВО! Датасет сохранен в {self.output_path}")

if __name__ == "__main__":
    labeler = AutoLabeler("database", "labeled_dataset")
    labeler.process_dataset()