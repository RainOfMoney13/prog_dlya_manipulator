import os, cv2, numpy as np, yaml
def process_dataset(input_path="database", output_path="labeled_dataset"):
    # Создание папок
    os.makedirs(f"{output_path}/images/train", exist_ok=True)
    os.makedirs(f"{output_path}/labels/train", exist_ok=True)
    print("Автоматическая разметка завершена (Заглушка)")