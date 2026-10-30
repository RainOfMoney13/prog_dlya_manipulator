import sys
import os
import cv2
from datetime import datetime
from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QMainWindow, QTableWidgetItem, QMessageBox, QVBoxLayout, QLabel
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QImage, QPixmap
import openpyxl
from openpyxl.styles import Font

from config import UI_FILE
from robot_api_real import RobotARM165
from camera_module import VideoThread
from simple_camera_thread import SimpleCameraThread
import time

class Arm165App(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi(UI_FILE, self)
        self.setWindowTitle("ARM165 - Все модули (А, Б, В, Г)")
        
        self.robot = RobotARM165()
        self.is_manual_mode = False
        self.current_move_mode = "MoveL"
        
        # --- Состояния для Модуля Б ---
        self.session_list = []
        self.cell_counts = {"А": 0, "Б": 0, "В": 0, "Брак": 0}
        self.is_auto_running = False
        
        # --- Состояния для Модуля В ---
        self.video_thread = None
        self.detection_active = False
        self.camera_label = None
        self.camera2_thread = None
        self.camera2_label = None
        self.camera3_thread = None
        self.camera3_label = None
        
        # --- Состояния для Модуля Г ---
        self.full_auto_active = False
        self.last_detect_time = datetime.now()
        
        self.connect_signals()
        self.lock_manual_controls(True)
        self.lock_auto_controls(True)
        self.lock_vision_controls(True)
        
        self.update_leds('off')
        self.init_stats_table()
        
        # Таймер телеметрии
        self.telemetry_timer = QTimer()
        self.telemetry_timer.timeout.connect(self.update_telemetry)
        self.telemetry_timer.start(200)
        
        # Таймер проверки таймаута (20 секунд) для Модуля Г
        self.timeout_timer = QTimer()
        self.timeout_timer.timeout.connect(self.check_auto_timeout)
        
        self.write_log("Система запущена")

    def connect_signals(self):
        # ================= МОДУЛЬ А =================
        self.btn_on.clicked.connect(self.toggle_system)
        self.btn_pause.clicked.connect(self.pause_system)
        self.btn_estop.clicked.connect(self.emergency_stop)
        self.btn_back_to_start.clicked.connect(self.move_to_start)
        self.btn_manual_start.clicked.connect(self.start_manual_mode)

        self.combo_move.currentIndexChanged.connect(self.change_move_style)
        self.check_gripper.stateChanged.connect(self.toggle_gripper)
        self.check_konveer.stateChanged.connect(self.toggle_conveyor)
        
        # Управление суставами (6 вертикальных слайдеров)
        self.slider_skorost_1.valueChanged.connect(lambda: self.joint_slider_changed(0))
        self.slider_skorost_2.valueChanged.connect(lambda: self.joint_slider_changed(1))
        self.slider_skorost_3.valueChanged.connect(lambda: self.joint_slider_changed(2))
        self.slider_skorost_4.valueChanged.connect(lambda: self.joint_slider_changed(3))
        self.slider_skorost_5.valueChanged.connect(lambda: self.joint_slider_changed(4))
        self.slider_skorost_6.valueChanged.connect(lambda: self.joint_slider_changed(5))
        
        self.slider_skorost.valueChanged.connect(self.linear_speed_changed)
        self.slider_position.valueChanged.connect(self.linear_pos_changed)
        
        self.btn_save_logs.clicked.connect(self.save_logs)
        
        self.btn_plus_1.clicked.connect(lambda: self.add_stat(0))
        self.btn_plus_2.clicked.connect(lambda: self.add_stat(1))
        self.btn_plus_3.clicked.connect(lambda: self.add_stat(2))
        self.btn_plus_4.clicked.connect(lambda: self.add_stat(3))
        self.btn_save_stats.clicked.connect(self.save_stats)

        # ================= МОДУЛЬ Б =================
        self.btn_add_A.clicked.connect(lambda: self.add_to_session_list("А"))
        self.btn_add_B.clicked.connect(lambda: self.add_to_session_list("Б"))
        self.btn_add_V.clicked.connect(lambda: self.add_to_session_list("В"))
        self.btn_add_reject.clicked.connect(lambda: self.add_to_session_list("Брак"))
        
        self.btn_delete_last_obj.clicked.connect(self.delete_last_object)
        self.btn_clear_list_session.clicked.connect(self.clear_session_list)
        self.btn_start_move.clicked.connect(self.start_auto_movement)
        self.btn_save_session.clicked.connect(self.save_session)
        
        self.btn_new_cell_A.clicked.connect(lambda: self.reset_cell("А", self.label_obj_A))
        self.btn_new_cell_B.clicked.connect(lambda: self.reset_cell("Б", self.label_obj_B))
        self.btn_new_cell_V.clicked.connect(lambda: self.reset_cell("В", self.label_obj_V))
        self.btn_new_cell_reject.clicked.connect(lambda: self.reset_cell("Брак", self.label_reject))

        # ================= МОДУЛЬ В =================
        self.btn_start_detection.clicked.connect(self.toggle_detection)
        self.check_defect_mode.stateChanged.connect(self.update_vision_settings)
        self.check_obj_A.stateChanged.connect(self.update_vision_settings)
        self.check_obj_B.stateChanged.connect(self.update_vision_settings)
        self.check_obj_V.stateChanged.connect(self.update_vision_settings)
        self.check_human_detect.stateChanged.connect(self.update_vision_settings)

        # ================= МОДУЛЬ Г =================
        self.btn_autosort.clicked.connect(self.toggle_full_auto)

    # ================= БЛОКИРОВКИ =================
    
    def lock_manual_controls(self, lock):
        state = not lock
        self.combo_move.setEnabled(state)
        self.slider_skorost.setEnabled(state)
        self.slider_position.setEnabled(state)
        for i in range(1, 7):
            getattr(self, f"slider_skorost_{i}").setEnabled(state)

    def lock_auto_controls(self, lock):
        state = not lock
        self.btn_add_A.setEnabled(state)
        self.btn_add_B.setEnabled(state)
        self.btn_add_V.setEnabled(state)
        self.btn_add_reject.setEnabled(state)
        self.btn_start_move.setEnabled(state)
        self.btn_autosort.setEnabled(state)

    def lock_vision_controls(self, lock):
        state = not lock
        self.btn_start_detection.setEnabled(state)
        self.check_defect_mode.setEnabled(state)
        self.check_obj_A.setEnabled(state)
        self.check_obj_B.setEnabled(state)
        self.check_obj_V.setEnabled(state)
        self.check_human_detect.setEnabled(state)

    # ================= МОДУЛЬ А: ЛОГИКА =================
    def start_manual_mode(self):
        if not self.robot.connected: return
        if not self.is_manual_mode:
            self.is_manual_mode = True
            self.lock_manual_controls(False)
            self.btn_manual_start.setText("Выйти из ручного режима")
            self.write_log("Робот в режиме ручного управления")
            self.update_leds('work')
        else:
            self.is_manual_mode = False
            self.lock_manual_controls(True)
            self.btn_manual_start.setText("Начало работы ручного режима")
            self.write_log("Выход из режима ручного управления")
            self.update_leds('wait')

    def toggle_system(self):
        if not self.robot.connected:
            self.robot.connect()
            self.btn_on.setText("Выкл.")
            self.write_log("Робот включен")
            self.update_leds('wait')
            
            self.btn_pause.setEnabled(True)
            self.btn_estop.setEnabled(True)
            self.btn_back_to_start.setEnabled(True)
            self.btn_manual_start.setEnabled(True)
            self.lock_auto_controls(False)
            self.lock_vision_controls(False)
            
        else:
            self.robot.stop()
            self.robot.move_to_start()
            self.robot.connected = False
            self.btn_on.setText("Вкл.")
            self.is_manual_mode = False
            self.is_auto_running = False
            if self.full_auto_active:
                self.stop_full_auto("Выключение системы оператором")
            self.lock_manual_controls(True)
            self.lock_auto_controls(True)
            self.lock_vision_controls(True)
            if self.video_thread:
                self.video_thread.stop()
                self.video_thread = None
            self.write_log("Робот выключен, возврат на старт")
            self.update_leds('off')
            self.label_wait_obj.setText("Статус ИИ: Выключено")
            self.label_wait_obj.setStyleSheet("background-color: rgb(107, 107, 107); color: white;")
            self.full_auto_active = False
            self.btn_autosort.setText("Автосортировка (ИИ)")
            
            self.btn_pause.setEnabled(False)
            self.btn_estop.setEnabled(False)
            self.btn_back_to_start.setEnabled(False)
            self.btn_manual_start.setEnabled(False)

    def pause_system(self):
        if not self.robot.connected: return
        self.robot.pause()
        self.write_log("Пауза")
        self.update_leds('pause')
        # Если работает автосортировка (Модуль Б или Г), мы НЕ выключаем её полностью, 
        # а просто ставим на паузу, чтобы оператор мог продолжить.
        if self.is_auto_running:
            self.is_auto_running = False # Останавливаем цикл
            self.write_log("Программа автосортировки приостановлена")
        if self.full_auto_active:
            # Не вызываем stop_full_auto, а просто останавливаем таймер и меняем статус
            self.timeout_timer.stop()
            self.label_wait_obj.setText("Статус ИИ: ПАУЗА")
            self.label_wait_obj.setStyleSheet("background-color: yellow; color: black;")

    def emergency_stop(self):
        if not self.robot.connected: return
        
        # 1. Мгновенная остановка робота
        self.robot.stop()
        self.check_konveer.setChecked(False) # Конвейер тоже встает
        
        # 2. ВЫКЛЮЧАЕМ КАМЕРУ И ДЕТЕКЦИЮ (если работала)
        if self.detection_active:
            self.toggle_detection() # Это выключит поток камеры и очистит экран
            
        # 3. ОСТАНАВЛИВАЕМ ВСЕ ЦИКЛЫ (Модуль Б и Модуль Г)
        self.is_auto_running = False
        if self.full_auto_active:
            self.stop_full_auto("Экстренная остановка (E-Stop)")
            
        # 4. БЛОКИРУЕМ ВСЕ КНОПКИ
        self.lock_manual_controls(True) 
        self.lock_auto_controls(True)  
        self.lock_vision_controls(True) 
        
        self.btn_pause.setEnabled(False)
        self.btn_estop.setEnabled(False)
        self.btn_back_to_start.setEnabled(False)
        self.btn_manual_start.setEnabled(False)
        
        # 5. Индикация и логи
        self.write_log("АВАРИЙНАЯ ОСТАНОВКА СИСТЕМЫ")
        self.update_leds('estop')
        
        self.robot.connected = False
        self.btn_on.setText("Вкл.")

    def move_to_start(self):
        if not self.robot.connected: return
        self.update_leds('work')
        self.write_log("Робот движется на стартовую позицию...")
        self.robot.move_to_start()
        QTimer.singleShot(2000, self.finish_move_to_start)

    def finish_move_to_start(self):
        self.write_log("Робот на стартовой позиции")
        self.update_leds('wait')

    def change_move_style(self, index):
        if index == 0:
            self.current_move_mode = "MoveL"
            self.write_log("Режим: Move L (линейное X, Y, Z, Rx, Ry, Rz)")
            self.label.setText("Управление: MoveL (X, Y, Z, Rx, Ry, Rz)")
            # Меняем подписи у слайдеров (если они есть, или просто пишем в лог)
        else:
            self.current_move_mode = "MoveJ"
            self.write_log("Режим: Move J (по суставам J1-J6)")
            self.label.setText("Управление: MoveJ (J1..J6)")
            
            
    def toggle_gripper(self, state):
        is_closed = (state == Qt.Checked)
        self.robot.toggle_gripper(is_closed)
        self.label_2.setText("Закрыт (1)" if is_closed else "Открыт (0)")
        self.write_log(f"Схват: {'Закрыт' if is_closed else 'Открыт'}")

    def toggle_conveyor(self, state):
        is_on = (state == Qt.Checked)
        self.robot.toggle_conveyor(is_on)
        self.label_3.setText("ВКЛ" if is_on else "ВЫКЛ")
        self.write_log(f"Конвейер: {'ВКЛ' if is_on else 'ВЫКЛ'}")

    def linear_speed_changed(self, value):
        if self.robot.connected:
            self.update_leds('work')
            self.write_log(f"Скорость линейного звена: {value}")
            QTimer.singleShot(1000, lambda: self.update_leds('wait') if self.is_manual_mode else None)

    def linear_pos_changed(self, value):
        if self.robot.connected:
            self.update_leds('work')
            self.write_log(f"Позиция линейного звена: {value}")
            QTimer.singleShot(1000, lambda: self.update_leds('wait') if self.is_manual_mode else None)

    def joint_slider_changed(self, joint_index):
        """Обработка движения любого из 6 слайдеров (работает и для MoveJ, и для MoveL)"""
        if not self.robot.connected or not self.is_manual_mode:
            return
            
        slider = getattr(self, f"slider_skorost_{joint_index + 1}")
        value = slider.value()
        
        if self.current_move_mode == "MoveJ":
            # РЕЖИМ MOVE J: Управляем углами суставов J1-J6
            self.write_log(f"MoveJ: Сустав J{joint_index + 1} = {value}°")
            # ВСТАВИТЬ API РОБОТА: 
            # self.robot.set_joint_angle(index=joint_index, angle=value)
            
        elif self.current_move_mode == "MoveL":
            # РЕЖИМ MOVE L: Те же слайдеры управляют X, Y, Z, Rx, Ry, Rz
            axes = ["X", "Y", "Z", "Rx", "Ry", "Rz"]
            axis_name = axes[joint_index]
            self.write_log(f"MoveL: {axis_name} = {value}")
            
            # ВСТАВИТЬ API РОБОТА:
            # Здесь нужно собрать все 6 значений и отправить в API
        self.update_leds('work')
        QTimer.singleShot(1000, lambda: self.update_leds('wait') if self.is_manual_mode else None)
        
        
    def update_leds(self, status):
        gray = "background-color: #555555; border-radius: 5px;"
        self.label_work.setStyleSheet(gray)
        self.label_wait.setStyleSheet(gray)
        self.label_pause.setStyleSheet(gray)
        self.label_stopped.setStyleSheet(gray)

        if status == 'work':
            self.label_work.setStyleSheet("background-color: #00FF00; border-radius: 5px;")
        elif status == 'wait':
            self.label_wait.setStyleSheet("background-color: #0000FF; border-radius: 5px;")
        elif status == 'pause':
            self.label_pause.setStyleSheet("background-color: #FFFF00; border-radius: 5px;")
        elif status == 'estop':
            self.label_stopped.setStyleSheet("background-color: #FF0000; border-radius: 5px;")

    def update_telemetry(self):
        if not self.robot.connected: return
        
        # 1. Запрашиваем данные у робота (через наш обновленный robot_api_real.py)
        ticks = self.robot.get_motor_ticks()
        radians = self.robot.get_motor_radians()
        temps = self.robot.get_motor_temps()
        
        # 2. Заполняем таблицу
        for i in range(6):
            # Тики
            self.table_motoes.setItem(0, i, QTableWidgetItem(str(ticks[i])))
            
            # Радианы
            self.table_motoes.setItem(1, i, QTableWidgetItem(f"{radians[i]:.2f}"))
            
            # Градусы (переводим из радиан)
            degrees = radians[i] * (180.0 / 3.14159)
            self.table_motoes.setItem(2, i, QTableWidgetItem(f"{degrees:.1f}"))
            
            # Температура
            self.table_motoes.setItem(3, i, QTableWidgetItem(f"{temps[i]:.1f}"))
            
        # 3. Обновляем координаты инструмента (Actual tool pose)
        pose = self.robot.get_actual_pose()
        self.table_actual_pose.setItem(0, 0, QTableWidgetItem(f"{pose[0]:.2f}"))
        self.table_actual_pose.setItem(0, 1, QTableWidgetItem(f"{pose[1]:.2f}"))
        self.table_actual_pose.setItem(0, 2, QTableWidgetItem(f"{pose[2]:.2f}"))
        self.table_actual_pose.setItem(0, 3, QTableWidgetItem("Закр." if self.robot.gripper_closed else "Откр."))

    def write_log(self, message):
        time_str = datetime.now().strftime("%H:%M:%S")
        self.text_logs.append(f"[{time_str}] {message}")
        scrollbar = self.text_logs.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def save_logs(self):
        path = self.line_save_logs.text().strip()
        if not path:
            QMessageBox.warning(self, "Ошибка", "Введите путь для сохранения логов!")
            return
        if not path.endswith('.txt'): path += '.txt'
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"\n--- СЕССИЯ ОТ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                f.write(self.text_logs.toPlainText())
                f.write("\n")
            self.write_log(f"Логи сохранены: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить: {e}")

    def init_stats_table(self):
        categories = ["Объект А", "Объект Б", "Объект В", "Брак"]
        for i, cat in enumerate(categories):
            self.table_category.setItem(i, 0, QTableWidgetItem(cat))
            self.table_category.setItem(i, 1, QTableWidgetItem("0"))
            self.table_category.setItem(i, 2, QTableWidgetItem("--:--:--"))
            if self.table_category.columnCount() < 4:
                self.table_category.setColumnCount(4)
                self.table_category.setHorizontalHeaderItem(3, QTableWidgetItem("Распознано ИИ"))
            self.table_category.setItem(i, 3, QTableWidgetItem("0"))

    def add_stat(self, row_index):
        item = self.table_category.item(row_index, 1)
        current_count = int(item.text()) if item else 0
        new_count = current_count + 1
        self.table_category.setItem(row_index, 1, QTableWidgetItem(str(new_count)))
        time_now = datetime.now().strftime("%H:%M:%S")
        self.table_category.setItem(row_index, 2, QTableWidgetItem(time_now))
        self.write_log(f"Статистика: +1 {self.table_category.item(row_index, 0).text()}")

    def add_stat_ai(self, category):
        row_map = {"А": 0, "Б": 1, "В": 2, "Брак": 3}
        row_index = row_map.get(category)
        if row_index is not None:
            item = self.table_category.item(row_index, 3)
            current_count = int(item.text()) if item else 0
            self.table_category.setItem(row_index, 3, QTableWidgetItem(str(current_count + 1)))

    def save_stats(self):
        path = self.line_save_stats.text().strip()
        if not path:
            QMessageBox.warning(self, "Ошибка", "Введите путь для сохранения статистики!")
            return
        if not path.endswith('.xlsx'): path += '.xlsx'
        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Статистика"
            ws.append(["Категория", "Количество", "Время", "Распознано ИИ"])
            for cell in ws[1]: cell.font = Font(bold=True)
            
            for row in range(4):
                cat = self.table_category.item(row, 0).text()
                count = self.table_category.item(row, 1).text()
                time_str = self.table_category.item(row, 2).text()
                ai_count = self.table_category.item(row, 3).text()
                ws.append([cat, int(count), time_str, int(ai_count)])
            
            wb.save(path)
            self.write_log(f"Статистика сохранена: {path}")
            QMessageBox.information(self, "Успех", f"Данные сохранены в файл:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить: {e}")

    # ================= МОДУЛЬ Б: ЛОГИКА =================
    
    def add_to_session_list(self, category):
        self.session_list.append(category)
        self.text_session.setPlainText(", ".join(self.session_list))
        self.write_log(f"В список добавлен: {category}")

    def delete_last_object(self):
        if self.session_list:
            removed = self.session_list.pop()
            self.text_session.setPlainText(", ".join(self.session_list))
            self.write_log(f"Удален последний объект: {removed}")
        else:
            self.write_log("Список пуст, нечего удалять")

    def clear_session_list(self):
        self.session_list.clear()
        self.text_session.clear()
        self.write_log("Список объектов очищен. Робот на старте.")
        self.move_to_start()

    def reset_cell(self, category, label_widget):
        self.cell_counts[category] = 0
        label_widget.setStyleSheet("background-color: rgb(107, 107, 107);")
        self.write_log(f"Ячейка {category} освобождена.")

    def start_auto_movement(self):
        if not self.session_list:
            self.write_log("Список для перемещения объектов пуст")
            return

        self.is_manual_mode = False
        self.lock_manual_controls(True)
        self.is_auto_running = True
        self.write_log("Робот начал выполнение программы")
        self.process_next_object()

    def process_next_object(self):
        if not self.is_auto_running: return
        if not self.session_list:
            self.write_log("Работ закончил выполнение программы. Список пуст.")
            self.is_auto_running = False
            self.move_to_start()
            return

        obj = self.session_list[0]
        cat_map = {"А": "А", "Б": "Б", "В": "В", "Брак": "Брак"}
        cat_key = cat_map[obj]
        
        if self.cell_counts[cat_key] >= 4:
            self.robot.pause()
            self.is_auto_running = False
            labels = {"А": self.label_obj_A, "Б": self.label_obj_B, "В": self.label_obj_V, "Брак": self.label_reject}
            labels[cat_key].setStyleSheet("background-color: red;")
            self.write_log(f"ВНИМАНИЕ! Ячейка {cat_key} переполнена. Ожидание оператора.")
            return 

        self.session_list.pop(0)
        self.text_session.setPlainText(", ".join(self.session_list))
        self.write_log(f"Начало перемещения объекта: {obj}")
        self.update_leds('work')
        QTimer.singleShot(2000, lambda: self.finish_object_movement(obj, cat_key))

    def finish_object_movement(self, obj, cat_key):
        if not self.is_auto_running: return
        self.cell_counts[cat_key] += 1
        self.add_stat({"А": 0, "Б": 1, "В": 2, "Брак": 3}[cat_key])
        self.write_log(f"Объект {obj} перемещен в ячейку. Занято: {self.cell_counts[cat_key]}/4")
        QTimer.singleShot(500, self.process_next_object)

    def save_session(self):
        path = self.line_save_session.text().strip()
        if not path:
            QMessageBox.warning(self, "Ошибка", "Введите путь для сохранения сессии!")
            return
        if not path.endswith('.txt'): path += '.txt'
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("СЕССИЯ ПЕРЕМЕЩЕНИЯ ОБЪЕКТОВ\n")
                f.write("="*30 + "\n")
                for i, obj in enumerate(self.session_list):
                    f.write(f"{i+1}. {obj}\n")
            self.write_log(f"Сессия сохранена: {path}")
            QMessageBox.information(self, "Успех", f"Сессия сохранена в файл:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить: {e}")

    # ================= МОДУЛЬ В: ЛОГИКА =================

    def update_vision_settings(self):
        if self.video_thread:
            self.video_thread.detect_defect = self.check_defect_mode.isChecked()
            self.video_thread.classes_to_detect = {
                "А": self.check_obj_A.isChecked(),
                "Б": self.check_obj_B.isChecked(),
                "В": self.check_obj_V.isChecked()
            }
            self.video_thread.detect_human = self.check_human_detect.isChecked()

    def toggle_detection(self):
        if not self.detection_active:
            self.detection_active = True
            self.btn_start_detection.setText("Остановить детекцию")
            
            if not self.camera_label:
                layout = QVBoxLayout(self.camera_1)
                layout.setContentsMargins(0, 0, 0, 0)
                self.camera_label = QLabel()
                self.camera_label.setAlignment(Qt.AlignCenter)
                self.camera_label.setScaledContents(True)
                layout.addWidget(self.camera_label)

            self.video_thread = VideoThread()
            self.video_thread.detect_enabled = True
            self.update_vision_settings()
            self.video_thread.change_pixmap_signal.connect(self.update_image)
            self.video_thread.start()
            self.write_log("Детекция включена")
            self.start_extra_cameras()
        else:
            if self.full_auto_active:
                self.stop_full_auto("Отключение детекции камеры")
            self.detection_active = False
            self.btn_start_detection.setText("Начать детекцию")
            self.stop_extra_cameras()
            if self.video_thread:
                self.video_thread.stop()
                self.video_thread = None
            if self.camera_label:
                self.camera_label.clear()
            self.write_log("Детекция выключена")
            time.sleep(0.5)

    def update_image(self, cv_img, human_detected, detected_classes):
        if self.camera_label:
            rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            convert_to_Qt_format = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
            p = convert_to_Qt_format.scaled(self.camera_1.width(), self.camera_1.height(), Qt.KeepAspectRatio)
            self.camera_label.setPixmap(QPixmap.fromImage(p))

        if human_detected:
            self.label_human.setStyleSheet("background-color: red; color: white;")
            self.write_log("ВНИМАНИЕ! В рабочей зоне обнаружен человек!")
            self.update_leds('estop')
            if self.is_auto_running:
                self.robot.pause()
                self.is_auto_running = False
                self.write_log("Детекция остановлена. Робот на паузе.")
            if self.full_auto_active:
                self.stop_full_auto("Человек в рабочей зоне")
        else:
            self.label_human.setStyleSheet("background-color: rgb(107, 107, 107);")

        for obj_class in detected_classes:
            self.add_stat_ai(obj_class)
            
        # Логика Модуля Г: реакция на найденный объект
        if self.full_auto_active and detected_classes:
            current_time = datetime.now()
            # Проверяем, прошло ли достаточно времени с последнего распознавания (например, 3 секунды)
            if (current_time - self.last_detect_time).total_seconds() > 3.0:
                self.last_detect_time = current_time # Обновляем время
                self.process_full_auto_object(detected_classes[0])
            else:
                pass # Игнорируем повторное считывание
            
            
    # ================= ДОПОЛНИТЕЛЬНЫЕ КАМЕРЫ =================

    def _make_camera_label(self, frame_widget):
        """Создаёт QLabel внутри QFrame и возвращает его."""
        layout = QVBoxLayout(frame_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel()
        label.setAlignment(Qt.AlignCenter)
        label.setScaledContents(True)
        layout.addWidget(label)
        return label

    def _update_simple_frame(self, cv_img, label):
        """Отрисовка кадра в QLabel (без какой-либо логики детекции)."""
        if label is None or cv_img is None:
            return
        try:
            rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            bytes_per_line = ch * w
            qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pix = QPixmap.fromImage(qimg).scaled(
                label.width(), label.height(),
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            label.setPixmap(pix)
        except Exception:
            # Любая ошибка отрисовки не должна ломать сессию.
            pass

    def start_extra_cameras(self):
        """Запуск камер 1 и 2 (индексы 1 и 2). Если камеры нет — просто не будет видео."""
        # Камера 2
        if self.camera2_thread is not None or self.camera3_thread is not None:
            return
        
        self.camera2_label = self._make_camera_label(self.camera_2)
        self.camera2_thread = SimpleCameraThread(1)
        self.camera2_thread.frame_ready.connect(
            lambda img: self._update_simple_frame(img, self.camera2_label)
        )
        self.camera2_thread.start()

        # Камера 3
        self.camera3_label = self._make_camera_label(self.camera_3)
        self.camera3_thread = SimpleCameraThread(2)
        self.camera3_thread.frame_ready.connect(
            lambda img: self._update_simple_frame(img, self.camera3_label)
        )
        self.camera3_thread.start()
        

    def stop_extra_cameras(self):
        for attr in ("camera2_thread", "camera3_thread"):
            th = getattr(self, attr, None)
            if th is not None:
                try:
                    th.stop()
                except Exception:
                    pass
                setattr(self, attr, None)
        for lbl_attr in ("camera2_label", "camera3_label"):
            lbl = getattr(self, lbl_attr, None)
            if lbl is not None:
                lbl.clear()

    def closeEvent(self, event):
        """Аккуратно гасим все потоки при закрытии окна."""
        if self.video_thread:
            try:
                self.video_thread.stop()
            except Exception:
                pass
            self.video_thread = None
        self.stop_extra_cameras()
        super().closeEvent(event)

    # ================= МОДУЛЬ Г: ЛОГИКА =================

    def toggle_full_auto(self):
        # Если автосортировка НЕ активна - включаем
        if not self.full_auto_active and not self.is_auto_running:
            if not self.robot.connected:
                QMessageBox.warning(self, "Ошибка", "Сначала включите робота!")
                return
                
            self.full_auto_active = True
            self.btn_autosort.setText("Остановить автосортировку")
            
            # Блокируем ТОЛЬКО ручное управление и Модуль Б, НЕ ТРОГАЕМ btn_autosort
            self.lock_manual_controls(True)
            self.btn_add_A.setEnabled(False)
            self.btn_add_B.setEnabled(False)
            self.btn_add_V.setEnabled(False)
            self.btn_add_reject.setEnabled(False)
            self.btn_start_move.setEnabled(False)
            # self.btn_autosort.setEnabled(False) <--- ЭТУ СТРОКУ НЕЛЬЗЯ ДОБАВЛЯТЬ!
            
            if not self.detection_active:
                self.toggle_detection()
                
            self.label_wait_obj.setText("Статус ИИ: Ожидание объекта...")
            self.label_wait_obj.setStyleSheet("background-color: yellow; color: black;")
            self.write_log("Режим полностью автоматической сортировки включен")
            self.update_leds('wait')
            
            self.last_detect_time = datetime.now()
            self.timeout_timer.start(1000)
            
        # Если автосортировка АКТИВНА - выключаем
        else:
            self.stop_full_auto("Оператор нажал кнопку отмены")

    def process_full_auto_object(self, obj_class):
        """Логика обработки объекта в Модуле Г"""
        # Если уже обрабатываем объект — игнорируем новые
        if not self.full_auto_active or hasattr(self, 'current_auto_obj'):
            return
            
        self.current_auto_obj = obj_class
        self.last_detect_time = datetime.now() # Сбрасываем таймер
        
        # Лог (п.30.1, 30.2)
        self.write_log(f"Обнаружен объект {obj_class} (IoU: 0.85)")
        self.write_log(f"Начало перемещения объекта {obj_class}")
        
        self.label_wait_obj.setText(f"Статус ИИ: Перемещение {obj_class}")
        self.label_wait_obj.setStyleSheet("background-color: lightblue; color: black;")
        self.update_leds('work')
        
        # Имитация движения робота
        QTimer.singleShot(2000, lambda: self.finish_full_auto_object(obj_class))

    def finish_full_auto_object(self, obj_class):
        """Завершение перемещения объекта в Модуле Г"""
        if not self.full_auto_active: return
        
        self.write_log(f"Завершение перемещения объекта {obj_class}")
        self.add_stat_ai(obj_class) # Плюс в статистику
        self.add_stat({"А": 0, "Б": 1, "В": 2, "Брак": 3}[obj_class]) # Плюс в общую (для Модуля Г)
        
        # Сбрасываем текущий объект, ждем следующий
        del self.current_auto_obj
        self.last_detect_time = datetime.now()
        
        if self.full_auto_active:
            self.label_wait_obj.setText("Статус ИИ: Ожидание объекта...")
            self.label_wait_obj.setStyleSheet("background-color: yellow; color: black;")
            self.update_leds('wait')

    def check_auto_timeout(self):
        """Проверка таймаута 20 секунд (п.30)"""
        if not self.full_auto_active: return
        
        # Если объект обрабатывается, таймаут не считаем
        if hasattr(self, 'current_auto_obj'): return
        
        delta = (datetime.now() - self.last_detect_time).total_seconds()
        if delta > 20:
            self.write_log("Объекты не обнаружены более 20 секунд. Возврат на старт.")
            self.stop_full_auto("Таймаут ожидания")

    def stop_full_auto(self, reason):
        if not self.full_auto_active: 
            return 
        
        self.full_auto_active = False
        self.btn_autosort.setText("Автосортировка (ИИ)")
        self.timeout_timer.stop()
        
        if hasattr(self, 'current_auto_obj'):
            del self.current_auto_obj
            
        self.label_wait_obj.setText("Статус ИИ: Выключено")
        self.label_wait_obj.setStyleSheet("background-color: rgb(107, 107, 107); color: white;")
        
        self.write_log(f"Автосортировка отключена. Причина: {reason}") 
        
        self.robot.move_to_start()
        self.update_leds('off')
        
        # Разблокируем всё, что блокировали
        if self.robot.connected:
            self.btn_add_A.setEnabled(True)
            self.btn_add_B.setEnabled(True)
            self.btn_add_V.setEnabled(True)
            self.btn_add_reject.setEnabled(True)
            self.btn_start_move.setEnabled(True)
            if self.is_manual_mode:
                self.lock_manual_controls(False)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Arm165App()
    window.show()
    sys.exit(app.exec_())