import os
import yaml
from ultralytics import YOLO
import torch
import shutil

def train_model():
    print("="*60)
    print("ЗАПУСК ОБУЧЕНИЯ МОДЕЛИ YOLO")
    print("="*60)

    # 1. Проверяем наличие конфигурационного файла датасета
    dataset_yaml = "labeled_dataset/dataset.yaml"
    if not os.path.exists(dataset_yaml):
        print(f"ОШИБКА: Файл {dataset_yaml} не найден!")
        print("Сначала запустите auto_labeling.py, чтобы создать датасет.")
        return

    # 2. Определяем устройство (Видеокарта или Процессор)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Обучение будет проходить на: {device.upper()}")

    # 3. Загружаем предобученную модель (yolov8n — самая быстрая, подойдет для старта)
    print("Загрузка базовой модели yolov8n.pt...")
    model = YOLO('yolov8n.pt')

    # 4. Запускаем обучение
    print("Начинаем обучение (это может занять время)...")
    try:
        results = model.train(
            data=dataset_yaml,  # Путь к нашему YAML
            epochs=50,          # Количество эпох (на конкурсе можно поставить 100)
            imgsz=640,          # Размер изображения
            batch=8,            # Размер батча (уменьшите до 4, если не хватает памяти)
            device=device,      # GPU или CPU
            project="runs/train", # Куда сохранять результаты
            name="defect_model",  # Имя папки с результатами
            exist_ok=True,      # Перезаписывать, если такая папка есть
            patience=15,        # Остановиться, если 15 эпох нет улучшений
            verbose=True
        )
        
        # 5. Копируем лучшую модель в удобное место
        best_model_path = "runs/train/defect_model/weights/best.pt"
        if os.path.exists(best_model_path):
            os.makedirs("trained_models", exist_ok=True)
            final_path = "trained_models/best_defect_model.pt"
            shutil.copy(best_model_path, final_path)
            print("\n" + "="*60)
            print(f"ОБУЧЕНИЕ ЗАВЕРШЕНО УСПЕШНО!")
            print(f"Лучшая модель сохранена по пути: {final_path}")
            print("="*60)
        else:
            print("Обучение завершилось, но файл весов best.pt не найден.")
            
    except Exception as e:
        print(f"ОШИБКА ПРИ ОБУЧЕНИИ: {e}")

if __name__ == "__main__":
    train_model()