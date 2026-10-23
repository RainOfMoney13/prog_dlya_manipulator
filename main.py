import sys
import os
import cv2
import numpy as np
from datetime import datetime
from PyQt5 import uic
from PyQt5.QtWidgets import *
from PyQt5.QtWidgets import QScrollArea
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QPixmap, QImage, QFont

from config import UI_FILE
from color_defect_detector import ColorDefectDetector
from camera_module import CameraThread
from robot_api_real import RobotARM165

class Arm165App(QDialog):
    def __init__(self):
        super().__init__()
        
        # 1. Загрузка интерфейса
        uic.loadUi(UI_FILE, self)
        self.setWindowTitle("ARM165 - Система управления")
        
        # 2. Инициализация компонентов
        self.robot = RobotARM165()
        self.detector = ColorDefectDetector()
        self.camera_threads = []
        self.camera_labels = {} # Храним ссылки на QLabel для камер
        self.auto_list = []
        
        # 3. Связывание сигналов (кнопок)
        self.connect_signals()
        
        # 4. Таймеры
        self.ui_timer = QTimer()
        self.ui_timer.timeout.connect(self.update_ui_status)
        self.ui_timer.start(100) # 10 раз в секунду

        # Запуск тестового лога
        self.log("Система инициализирована")
        
        

    def connect_signals(self):
        # --- Модуль А: Управление ---
        self.btn_on.clicked.connect(self.system_on)
        self.btn_stop.clicked.connect(self.system_stop)
        self.btn_pause.clicked.connect(self.system_pause)
        self.btn_start_pose.clicked.connect(self.move_to_start)
        
        self.btn_manual_cart.clicked.connect(lambda: self.robot.manual_cart_mode() if hasattr(self.robot, 'manual_cart_mode') else self.log("Ручной режим"))
        self.btn_manual_joint.clicked.connect(lambda: self.robot.manual_joint_mode() if hasattr(self.robot, 'manual_joint_mode') else self.log("Ручной режим"))

        # --- Камеры (3 шт) ---
        # Кнопки btn_3motora и btn_6motorov используются для запуска камер
        self.btn_3motora.clicked.connect(lambda: self.start_camera(0))
        self.btn_6motorov.clicked.connect(lambda: self.start_camera(1))
        # Для 3-й камеры можно использовать свободную кнопку (например, btn_add_point)
        self.btn_add_point.clicked.connect(lambda: self.start_camera(2))

        # --- Модуль Б: Автоматика ---
        self.btn_run_session.clicked.connect(self.start_auto_sorting)
        self.btn_clear_session.clicked.connect(self.clear_session_list)

        # --- Логи ---
        self.btn_save_logs.clicked.connect(self.save_logs)

    # ================= ЛОГИКА РОБОТА =================
    def system_on(self):
        self.robot.connect()
        self.btn_on.setText("Выкл.")
        self.log("Робот включен")

    def system_stop(self):
        # ВСТАВИТЬ API РОБОТА: self.robot.stop()
        self.log("Экстренная остановка!")
        self.btn_on.setText("Вкл.")

    def system_pause(self):
        # ВСТАВИТЬ API РОБОТА: self.robot.pause()
        self.log("Пауза")

    def move_to_start(self):
        # ВСТАВИТЬ API РОБОТА: self.robot.moveToStart()
        self.log("Робот едет на стартовую позицию")

    # ================= КАМЕРЫ =================
    def start_camera(self, cam_id):
        if cam_id in self.camera_labels:
            self.log(f"Камера {cam_id+1} уже запущена")
            return

        thread = CameraThread(cam_id, process_vision=True)
        thread.frame_signal.connect(self.display_camera_frame)
        thread.start()
        self.camera_threads.append(thread)
        self.log(f"Камера {cam_id+1} запущена")

    def display_camera_frame(self, cam_id, frame, defects):
        # Определяем, в какой QFrame выводить
        if cam_id == 0: container = self.camera1
        elif cam_id == 1: container = self.camera2
        else: container = self.camera3

        # Создаем QLabel внутри QFrame один раз
        if cam_id not in self.camera_labels:
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0,0,0,0)
            label = QLabel()
            label.setAlignment(Qt.AlignCenter)
            label.setScaledContents(True)
            layout.addWidget(label)
            self.camera_labels[cam_id] = label
            container.setLayout(layout)

        # Конвертация кадра
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        qt_img = QImage(rgb_image.data, w, h, ch * w, QImage.Format_RGB888)
        
        # Отображение
        self.camera_labels[cam_id].setPixmap(QPixmap.fromImage(qt_img))

    # ================= АВТОМАТИКА (Модуль Б) =================
    def clear_session_list(self):
        self.auto_list.clear()
        self.text_session.clear()
        self.log("Список очищен")

    def start_auto_sorting(self):
        if not self.auto_list:
            self.log("Ошибка: Список пуст")
            return
        
        self.log("Начало автоматической сортировки")
        self.btn_run_session.setEnabled(False)
        self.process_next_object()

    def process_next_object(self):
        if not self.auto_list:
            self.log("Сортировка завершена")
            self.btn_run_session.setEnabled(True)
            return

        obj = self.auto_list.pop(0)
        self.text_session.setText(", ".join(self.auto_list))
        self.log(f"Перемещение объекта: {obj}")
        
        # =========================================================
        # ВСТАВИТЬ API РОБОТА ЗДЕСЬ
        # self.robot.move_to_point(obj.x, obj.y, obj.z)
        # self.robot.gripper_on()
        # =========================================================
        
        # Имитация работы
        QTimer.singleShot(2000, self.finish_object_movement)

    def finish_object_movement(self):
        self.log("Объект перемещен")
        self.process_next_object()

    # ================= ВСПОМОГАТЕЛЬНЫЕ =================
    def update_ui_status(self):
        # Обновление таблицы (имитация)
        # В реальности здесь вызовы self.robot.get_position() и т.д.
        pass

    def log(self, message):
        time_str = datetime.now().strftime("%H:%M:%S")
        self.text_log.append(f"[{time_str}] {message}")
        # Автопрокрутка
        scrollbar = self.text_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def save_logs(self):
        path = self.text_save_logs.toPlainText()
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.text_log.toPlainText())
            self.log(f"Логи сохранены в {path}")

    def closeEvent(self, event):
        for thread in self.camera_threads:
            thread.stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = Arm165App()
    window.show()
    sys.exit(app.exec_())