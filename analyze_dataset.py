import os, cv2
def analyze_dataset(path="database"):
    if not os.path.exists(path): return
    files = [f for f in os.listdir(path) if f.endswith(('.jpg', '.png'))]
    print(f"Найдено {len(files)} изображений")