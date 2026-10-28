import os
import cv2
import numpy as np
import yaml

class AutoLabeler:
    def __init__(self, input_path="database", output_path="labeled_dataset"):
        self.input_path = input_path
        self.output_path = output_path
        
        # Словарь: название папки -> ID класса для YOLO (0, 1, 2, 3)
        self.classes_map = {
            "A": 0,
            "B": 1,
            "V": 2,
            "reject": 3
        }
        self.class_names = ["object_A", "object_B", "object_V", "defect"]
        
        # Создаем папки для YOLO
        for folder in ["images/train", "images/val", "labels/train", "labels/val"]:
            os.makedirs(os.path.join(self.output_path, folder), exist_ok=True)

    def detect_objects(self, image):
        """Автоматическое обнаружение объектов (по контрасту/контурам)"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        
        kernel = np.ones((5,5), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=1)
        
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        bboxes = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if 500 < area < 50000:
                x, y, w, h = cv2.boundingRect(cnt)
                bboxes.append([x, y, w, h])
        return bboxes

    def process_dataset(self):
        print("Начинаем авторазметку...")
        
        all_images = [] # Сюда соберем (путь_к_файлу, id_класса)
        
        # 1. Проходимся по всем папкам (A, B, V, reject)
        for folder_name, class_id in self.classes_map.items():
            folder_path = os.path.join(self.input_path, folder_name)
            if not os.path.exists(folder_path):
                print(f"ПРЕДУПРЕЖДЕНИЕ: Папка {folder_path} не найдена. Пропускаем.")
                continue
                
            files = [f for f in os.listdir(folder_path) if f.endswith(('.jpg', '.png', '.jpeg'))]
            print(f"Найдено {len(files)} фото в папке {folder_name} (класс {class_id})")
            
            for f in files:
                all_images.append((os.path.join(folder_path, f), class_id))
                
        if not all_images:
            print("ОШИБКА: Не найдено ни одного фото в папках A, B, V, reject!")
            return

        # Перемешиваем, чтобы в train и val попали разные классы
        import random
        random.shuffle(all_images)
        
        split_idx = int(len(all_images) * 0.8) # 80% на обучение, 20% на проверку
        
        for idx, (img_path, class_id) in enumerate(all_images):
            image = cv2.imread(img_path)
            if image is None: continue
            
            h_img, w_img = image.shape[:2]
            split = "train" if idx < split_idx else "val"
            filename = os.path.basename(img_path)
            
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
                    x_center = (x + w/2) / w_img
                    y_center = (y + h/2) / h_img
                    w_norm = w / w_img
                    h_norm = h / h_img
                    # ПИШЕМ ПРАВИЛЬНЫЙ КЛАСС (0, 1, 2 или 3)
                    f.write(f"{class_id} {x_center:.6f} {y_center:.6f} {w_norm:.6f} {h_norm:.6f}\n")
            
            if idx % 10 == 0:
                print(f"Обработано {idx}/{len(all_images)}")

        # 3. Создаем файл конфигурации для YOLO
        config = {
            'path': os.path.abspath(self.output_path),
            'train': 'images/train',
            'val': 'images/val',
            'names': {i: name for i, name in enumerate(self.class_names)}
        }
        with open(os.path.join(self.output_path, "dataset.yaml"), 'w') as f:
            yaml.dump(config, f)

        print(f"\nГОТОВО! Датасет сохранен в {self.output_path}")

if __name__ == "__main__":
    labeler = AutoLabeler("database", "labeled_dataset")
    labeler.process_dataset()