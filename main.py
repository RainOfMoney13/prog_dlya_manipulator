import sys
import os
from datetime import datetime
from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QMainWindow, QTableWidgetItem, QMessageBox
from PyQt5.QtCore import QTimer, Qt
import openpyxl
from openpyxl.styles import Font

from config import UI_FILE
from robot_api_real import RobotARM165

class Arm165App(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi(UI_FILE, self)
        self.setWindowTitle("ARM165 - Ручной и Автоматический режим")
        
        self.robot = RobotARM165()
        self.is_manual_mode = False
        
        # --- Состояния для Модуля Б ---
        self.session_list = [] # Список объектов на перемещение
        self.cell_counts = {"А": 0, "Б": 0, "В": 0, "Брак": 0} # Заполненность ячеек
        self.is_auto_running = False # Запущен ли авторежим
        
        self.connect_signals()
        self.lock_manual_controls(True)
        self.lock_auto_controls(True) # Блокируем кнопки Модуля Б до включения системы
        
        self.update_leds('off')
        self.init_stats_table()
        
        # Таймер телеметрии (ТЗ п.7)
        self.telemetry_timer = QTimer()
        self.telemetry_timer.timeout.connect(self.update_telemetry)
        self.telemetry_timer.start(200)
        
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
        
        self.slider_skorost.valueChanged.connect(self.linear_speed_changed)
        self.slider_position.valueChanged.connect(self.linear_pos_changed)
        
        self.btn_save_logs.clicked.connect(self.save_logs)
        
        self.btn_plus_1.clicked.connect(lambda: self.add_stat(0))
        self.btn_plus_2.clicked.connect(lambda: self.add_stat(1))
        self.btn_plus_3.clicked.connect(lambda: self.add_stat(2))
        self.btn_plus_4.clicked.connect(lambda: self.add_stat(3))
        self.btn_save_stats.clicked.connect(self.save_stats)

        # ================= МОДУЛЬ Б =================
        # Добавление в список (п.12, 13)
        self.btn_add_A.clicked.connect(lambda: self.add_to_session_list("А"))
        self.btn_add_B.clicked.connect(lambda: self.add_to_session_list("Б"))
        self.btn_add_V.clicked.connect(lambda: self.add_to_session_list("В"))
        self.btn_add_reject.clicked.connect(lambda: self.add_to_session_list("Брак"))
        
        # Управление списком (п.14, 15)
        self.btn_delete_last_obj.clicked.connect(self.delete_last_object)
        self.btn_clear_list_session.clicked.connect(self.clear_session_list)
        
        # Запуск движения (п.19)
        self.btn_start_move.clicked.connect(self.start_auto_movement)
        
        # Сохранение сессии (п.16, 17)
        self.btn_save_session.clicked.connect(self.save_session)
        
        # Сброс ячеек (п.18.1)
        self.btn_new_cell_A.clicked.connect(lambda: self.reset_cell("А", self.label_obj_A))
        self.btn_new_cell_B.clicked.connect(lambda: self.reset_cell("Б", self.label_obj_B))
        self.btn_new_cell_V.clicked.connect(lambda: self.reset_cell("В", self.label_obj_V))
        self.btn_new_cell_reject.clicked.connect(lambda: self.reset_cell("Брак", self.label_reject))

    # ================= МОДУЛЬ А: ЛОГИКА =================
    
    def lock_manual_controls(self, lock):
        state = not lock
        self.combo_move.setEnabled(state)
        self.verticalSlider.setEnabled(state)
        self.verticalSlider_2.setEnabled(state)
        self.verticalSlider_3.setEnabled(state)
        self.verticalSlider_4.setEnabled(state)
        self.verticalSlider_5.setEnabled(state)
        self.verticalSlider_6.setEnabled(state)
        self.slider_skorost.setEnabled(state)
        self.slider_position.setEnabled(state)
        self.btn_manual_start.setEnabled(state)

    def lock_auto_controls(self, lock):
        """Блокирует кнопки Модуля Б, когда система выключена"""
        state = not lock
        self.btn_add_A.setEnabled(state)
        self.btn_add_B.setEnabled(state)
        self.btn_add_V.setEnabled(state)
        self.btn_add_reject.setEnabled(state)
        self.btn_start_move.setEnabled(state)

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
            
            # Разблокируем кнопки
            self.btn_pause.setEnabled(True)
            self.btn_estop.setEnabled(True)
            self.btn_back_to_start.setEnabled(True)
            self.btn_manual_start.setEnabled(True)
            self.lock_auto_controls(False) # Разблокируем Модуль Б
            
        else:
            self.robot.stop()
            self.robot.move_to_start()
            self.robot.connected = False
            self.btn_on.setText("Вкл.")
            self.is_manual_mode = False
            self.is_auto_running = False
            self.lock_manual_controls(True)
            self.lock_auto_controls(True) # Блокируем Модуль Б
            self.write_log("Робот выключен, возврат на старт")
            self.update_leds('off')
            
            # Блокируем кнопки
            self.btn_pause.setEnabled(False)
            self.btn_estop.setEnabled(False)
            self.btn_back_to_start.setEnabled(False)
            self.btn_manual_start.setEnabled(False)

    def pause_system(self):
        if not self.robot.connected: return
        self.robot.pause()
        self.write_log("Пауза")
        self.update_leds('pause')

    def emergency_stop(self):
        if not self.robot.connected: return
        self.robot.stop()
        self.check_konveer.setChecked(False)
        self.write_log("АВАРИЙНАЯ ОСТАНОВКА СИСТЕМЫ")
        self.update_leds('estop')
        self.is_auto_running = False # Прерываем авторежим

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
        style = self.combo_move.currentText()
        self.write_log(f"Режим управления: {style}")
        self.label.setText(f"Управление манипулятором ({'MoveL' if index == 0 else 'MoveJ'})")

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
        pose = self.robot.get_actual_pose()
        self.table_actual_pose.setItem(0, 0, QTableWidgetItem(f"{pose[0]:.2f}"))
        self.table_actual_pose.setItem(0, 1, QTableWidgetItem(f"{pose[1]:.2f}"))
        self.table_actual_pose.setItem(0, 2, QTableWidgetItem(f"{pose[2]:.2f}"))
        self.table_actual_pose.setItem(0, 3, QTableWidgetItem("Закр." if self.robot.gripper_closed else "Откр."))
        
        ticks = self.robot.get_motor_ticks()
        for i in range(6):
            self.table_motoes.setItem(0, i, QTableWidgetItem(str(ticks[i])))

    # ================= ЛОГИ И СТАТИСТИКА (Модуль А) =================

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

    def add_stat(self, row_index):
        item = self.table_category.item(row_index, 1)
        current_count = int(item.text()) if item else 0
        new_count = current_count + 1
        self.table_category.setItem(row_index, 1, QTableWidgetItem(str(new_count)))
        time_now = datetime.now().strftime("%H:%M:%S")
        self.table_category.setItem(row_index, 2, QTableWidgetItem(time_now))
        self.write_log(f"Статистика: +1 {self.table_category.item(row_index, 0).text()}")

    def save_stats(self):
        path = self.line_save_stats.text().strip()
        if not path:
            QMessageBox.warning(self, "Ошибка", "Введите путь для сохранения статистики!")
            return
        if not path.endswith('.xlsx'): path += '.xlsx'
        try:
            if os.path.exists(path):
                wb = openpyxl.load_workbook(path)
                ws = wb.active
                for row in range(2, 6):
                    for col in range(1, 4):
                        ws.cell(row=row, column=col).value = None
            else:
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "Статистика"
                ws.append(["Категория", "Количество", "Время"])
                for cell in ws[1]: cell.font = Font(bold=True)
                ws.column_dimensions['A'].width = 15
                ws.column_dimensions['B'].width = 15
                ws.column_dimensions['C'].width = 25
            
            for row in range(4):
                cat = self.table_category.item(row, 0).text()
                count = self.table_category.item(row, 1).text()
                time_str = self.table_category.item(row, 2).text()
                ws.cell(row=row+2, column=1).value = cat
                ws.cell(row=row+2, column=2).value = int(count)
                ws.cell(row=row+2, column=3).value = time_str
            
            wb.save(path)
            self.write_log(f"Статистика сохранена: {path}")
            QMessageBox.information(self, "Успех", f"Данные сохранены в файл:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить: {e}")

    # ================= МОДУЛЬ Б: ЛОГИКА =================

    def add_to_session_list(self, category):
        """Добавление объекта в очередь (п.12)"""
        self.session_list.append(category)
        self.text_session.setPlainText(", ".join(self.session_list))
        self.write_log(f"В список добавлен: {category}")

    def delete_last_object(self):
        """Удаление последнего добавленного (п.14)"""
        if self.session_list:
            removed = self.session_list.pop()
            self.text_session.setPlainText(", ".join(self.session_list))
            self.write_log(f"Удален последний объект: {removed}")
        else:
            self.write_log("Список пуст, нечего удалять")

    def clear_session_list(self):
        """Очистка списка (п.15)"""
        self.session_list.clear()
        self.text_session.clear()
        self.write_log("Список объектов очищен. Робот на старте.")
        self.move_to_start()

    def reset_cell(self, category, label_widget):
        """Сброс ячейки (п.18.1)"""
        self.cell_counts[category] = 0
        label_widget.setStyleSheet("background-color: rgb(107, 107, 107);")
        self.write_log(f"Ячейка {category} освобождена.")

    def start_auto_movement(self):
        """Запуск автосортировки (п.19)"""
        if not self.session_list:
            self.write_log("Список для перемещения объектов пуст")
            return

        self.is_manual_mode = False
        self.lock_manual_controls(True)
        self.is_auto_running = True
        self.write_log("Робот начал выполнение программы")
        self.process_next_object()

    def process_next_object(self):
        """Обработка следующего объекта из списка"""
        if not self.is_auto_running:
            return

        if not self.session_list:
            self.write_log("Работ закончил выполнение программы. Список пуст.")
            self.is_auto_running = False
            self.move_to_start()
            return

        # Берем первый объект
        obj = self.session_list[0] # Не удаляем сразу, чтобы проверить заполненность
        
        # Определяем индекс ячейки для проверки
        cat_map = {"А": "А", "Б": "Б", "В": "В", "Брак": "Брак"}
        cat_key = cat_map[obj]
        
        # ПРОВЕРКА ПЕРЕПОЛНЕНИЯ (ТЗ п.18.1)
        if self.cell_counts[cat_key] >= 4:
            self.robot.pause()
            self.is_auto_running = False
            
            # Включаем красную индикацию
            labels = {"А": self.label_obj_A, "Б": self.label_obj_B, "В": self.label_obj_V, "Брак": self.label_reject}
            labels[cat_key].setStyleSheet("background-color: red;")
            
            self.write_log(f"ВНИМАНИЕ! Ячейка {cat_key} переполнена. Ожидание оператора.")
            return # Ждем, пока оператор не нажмет кнопку

        # Если места хватает, имитируем перемещение
        self.session_list.pop(0)
        self.text_session.setPlainText(", ".join(self.session_list))
        
        self.write_log(f"Начало перемещения объекта: {obj}")
        self.update_leds('work')
        
        # ВСТАВИТЬ API РОБОТА ЗДЕСЬ
        # self.robot.move_to_point(obj_x, obj_y, obj_z)
        
        # Имитация задержки перемещения
        QTimer.singleShot(2000, lambda: self.finish_object_movement(obj, cat_key))

    def finish_object_movement(self, obj, cat_key):
        """Завершение перемещения одного объекта"""
        if not self.is_auto_running: return
        
        self.cell_counts[cat_key] += 1
        self.add_stat({"А": 0, "Б": 1, "В": 2, "Брак": 3}[cat_key]) # Автоматически обновляем статистику (п.12.2)
        
        self.write_log(f"Объект {obj} перемещен в ячейку. Занято: {self.cell_counts[cat_key]}/4")
        
        # Запускаем следующий
        QTimer.singleShot(500, self.process_next_object)

    def save_session(self):
        """Сохранение сессии в файл (п.16)"""
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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Arm165App()
    window.show()
    sys.exit(app.exec_())
