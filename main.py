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
        # Загружаем интерфейс
        uic.loadUi(UI_FILE, self)
        self.setWindowTitle("ARM165 - Ручной режим (Модуль А)")
        
        # Инициализация компонентов
        self.robot = RobotARM165()
        self.is_manual_mode = False
        self.btn_pause.setEnabled(False)
        self.btn_estop.setEnabled(False)
        self.btn_back_to_start.setEnabled(False)
        
        # 1. Связываем сигналы
        self.connect_signals()
        
        # 2. Блокируем джойстики (ТЗ п.1.5)
        self.lock_manual_controls(True)
        self.btn_manual.setEnabled(False)
        
        # 3. Настраиваем светофор
        self.update_leds('off')
        
        # 4. Инициализируем таблицу статистики
        self.init_stats_table()
        
        # 5. Таймер обновления телеметрии (ТЗ п.7)
        self.telemetry_timer = QTimer()
        self.telemetry_timer.timeout.connect(self.update_telemetry)
        self.telemetry_timer.start(200) # 5 раз в секунду
        
        self.write_log("Система запущена")

    def connect_signals(self):
        """Привязка ВСЕХ кнопок и элементов к функциям (строго по вашим именам)"""
        # --- П.1 Кнопки управления ---
        self.btn_on.clicked.connect(self.toggle_system)
        self.btn_pause.clicked.connect(self.pause_system)
        self.btn_estop.clicked.connect(self.emergency_stop)
        self.btn_back_to_start.clicked.connect(self.move_to_start)
        self.btn_manual.clicked.connect(self.start_manual_mode)

        # --- П.2, П.3, П.4 Управление ---
        self.combobox_move.currentIndexChanged.connect(self.change_move_style)
        self.checkbox_gripper.stateChanged.connect(self.toggle_gripper)
        self.checkbox_konveer.stateChanged.connect(self.toggle_conveyor)
        
        # --- П.5 Линейное звено ---
        self.slider_skorost.valueChanged.connect(self.linear_speed_changed)
        self.slider_postition.valueChanged.connect(self.linear_pos_changed)
        
        # --- П.9 Сохранение логов ---
        self.btn_save_logs.clicked.connect(self.save_logs)
        
        # --- П.10, П.11 Статистика ---
        self.btn_plus_1.clicked.connect(lambda: self.add_stat(0)) # Объект А
        self.btn_plus_2.clicked.connect(lambda: self.add_stat(1)) # Объект Б
        self.btn_plus_3.clicked.connect(lambda: self.add_stat(2)) # Объект В
        self.btn_plus_4.clicked.connect(lambda: self.add_stat(3)) # Брак
        self.btn_stats.clicked.connect(self.save_stats)

    # ================= ЛОГИКА УПРАВЛЕНИЯ =================
    
    def lock_manual_controls(self, lock):
        """Блокирует/разблокирует джойстики (ТЗ п.1.5)"""
        state = not lock
        self.combobox_move.setEnabled(state)
        self.slider_1.setEnabled(state)
        self.slider_2.setEnabled(state)
        self.slider_3.setEnabled(state)
        self.slider_4.setEnabled(state)
        self.slider_5.setEnabled(state)
        self.slider_6.setEnabled(state)
        self.slider_skorost.setEnabled(state)
        self.slider_postition.setEnabled(state)

    def start_manual_mode(self):
        if not self.is_manual_mode:
            # Включаем ручной режим
            self.is_manual_mode = True
            self.lock_manual_controls(False)
            self.btn_manual.setText("Выйти из ручного режима")
            self.write_log("Робот в режиме ручного управления")
            self.update_leds('wait')
        else:
            # Выключаем ручной режим
            self.is_manual_mode = False
            self.lock_manual_controls(True)
            self.btn_manual.setText("Начало работы ручного режима")
            self.write_log("Выход из режима ручного управления")
            self.update_leds('off')

    def toggle_system(self):
        if not self.robot.connected:
            # ВКЛЮЧАЕМ СИСТЕМУ
            self.robot.connect()
            self.btn_on.setText("Выкл.")
            self.write_log("Робот включен")
            self.update_leds('wait')
            
            # РАЗБЛОКИРУЕМ кнопки управления
            self.btn_manual.setEnabled(True)
            self.btn_pause.setEnabled(True)
            self.btn_estop.setEnabled(True)
            self.btn_back_to_start.setEnabled(True)
            
        else:
            # ВЫКЛЮЧАЕМ СИСТЕМУ
            self.robot.stop()
            self.robot.move_to_start()
            self.robot.connected = False
            self.btn_on.setText("Вкл.")
            
            # Если были в ручном режиме - принудительно выходим из него
            if self.is_manual_mode:
                self.is_manual_mode = False
                self.btn_manual.setText("Начало работы ручного режима")
                
            self.lock_manual_controls(True)
            self.write_log("Робот выключен, возврат на старт")
            self.update_leds('off')
            
            # БЛОКИРУЕМ кнопки управления движением
            self.btn_manual.setEnabled(False)
            self.btn_pause.setEnabled(False)
            self.btn_estop.setEnabled(False)
            self.btn_back_to_start.setEnabled(False)

    def pause_system(self):
        """Пауза (ТЗ п.1.2)"""
        self.robot.pause()
        self.write_log("Пауза") # ТЗ п.8.6
        self.update_leds('pause')

    def emergency_stop(self):
        """Экстренное торможение (ТЗ п.1.3)"""
        self.robot.stop()
        # При аварии конвейер тоже останавливается (ТЗ п.4)
        if self.checkbox_konveer.isChecked():
            self.checkbox_konveer.setChecked(False)
        self.write_log("АВАРИЙНАЯ ОСТАНОВКА СИСТЕМЫ") # ТЗ п.8.5
        self.update_leds('estop')

    def move_to_start(self):
        """Возврат на старт (ТЗ п.1.4)"""
        self.robot.move_to_start()
        self.write_log("Робот на стартовой позиции") # ТЗ п.8.2
        self.update_leds('wait')

    # ================= ПЕРЕКЛЮЧАТЕЛИ =================

    def change_move_style(self, index):
        """Переключение Move L / Move J (ТЗ п.2)"""
        style = self.combobox_move.currentText()
        self.write_log(f"Режим управления: {style}")
        self.label.setText(f"Управление манипулятором ({'MoveL' if index == 0 else 'MoveJ'})")

    def toggle_gripper(self, state):
        """Схват (ТЗ п.3)"""
        is_closed = (state == Qt.Checked)
        self.robot.toggle_gripper(is_closed)
        # Меняем подпись (0 - открыть / 1 - закрыть)
        self.label_2.setText("Закрыт (1)" if is_closed else "Открыт (0)")
        self.write_log(f"Схват: {'Закрыт' if is_closed else 'Открыт'}")

    def toggle_conveyor(self, state):
        """Конвейер (ТЗ п.4)"""
        is_on = (state == Qt.Checked)
        self.robot.toggle_conveyor(is_on)
        # Меняем подпись
        self.label_3.setText("ВКЛ" if is_on else "ВЫКЛ")
        self.write_log(f"Конвейер: {'ВКЛ' if is_on else 'ВЫКЛ'}")

    def linear_speed_changed(self, value):
        """Скорость линейного звена (ТЗ п.5)"""
        self.write_log(f"Скорость линейного звена: {value}")

    def linear_pos_changed(self, value):
        """Позиция линейного звена (ТЗ п.5)"""
        self.write_log(f"Позиция линейного звена: {value}")

    # ================= ИНДИКАЦИЯ И ТЕЛЕМЕТРИЯ =================

    def update_leds(self, status):
        """Управление светофором (ТЗ п.6)"""
        gray = "background-color: #555555; border-radius: 5px;"
        self.label_work.setStyleSheet(gray)
        self.label_wait.setStyleSheet(gray)
        self.label_pause.setStyleSheet(gray)
        self.label_stopped.setStyleSheet(gray)

        if status == 'work':
            self.label_work.setStyleSheet("background-color: #00FF00; border-radius: 5px;") # Зеленый
        elif status == 'wait':
            self.label_wait.setStyleSheet("background-color: #0000FF; border-radius: 5px;") # Синий
        elif status == 'pause':
            self.label_pause.setStyleSheet("background-color: #FFFF00; border-radius: 5px;") # Желтый
        elif status == 'estop':
            self.label_stopped.setStyleSheet("background-color: #FF0000; border-radius: 5px;") # Красный

    def update_telemetry(self):
        """Обновление таблиц с координатами (ТЗ п.7)"""
        if not self.robot.connected: return
        
        # Actual tool pose
        pose = self.robot.get_actual_pose()
        self.table_actual_tool_pose.setItem(0, 0, QTableWidgetItem(f"{pose[0]:.2f}"))
        self.table_actual_tool_pose.setItem(0, 1, QTableWidgetItem(f"{pose[1]:.2f}"))
        self.table_actual_tool_pose.setItem(0, 2, QTableWidgetItem(f"{pose[2]:.2f}"))
        self.table_actual_tool_pose.setItem(0, 3, QTableWidgetItem("Закр." if self.robot.gripper_closed else "Откр."))
        
        # Состояние моторов
        ticks = self.robot.get_motor_ticks()
        for i in range(6):
            self.table_motors.setItem(0, i, QTableWidgetItem(str(ticks[i])))

    # ================= ЛОГИ И СТАТИСТИКА =================

    def write_log(self, message):
        """Вывод логов в интерфейс (ТЗ п.8)"""
        time_str = datetime.now().strftime("%H:%M:%S")
        self.text_logs.append(f"[{time_str}] {message}")
        scrollbar = self.text_logs.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def save_logs(self):
        path = self.lineEdit.text().strip() 
        
        if not path:
            QMessageBox.warning(self, "Ошибка", "Введите путь для сохранения логов!")
            return
            
        # Если пользователь забыл расширение, добавляем .txt
        if not path.endswith('.txt'):
            path += '.txt'
            
        try:
            # ИЗМЕНЕНИЕ: Открываем файл в режиме 'a' (append - добавление).
            # Если файл существует, новые логи допишутся в конец.
            # Если файла нет, он создастся автоматически.
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"\n--- СЕССИЯ ОТ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                f.write(self.text_logs.toPlainText())
                f.write("\n")
                
            self.write_log(f"Логи сохранены/обновлены: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить: {e}")

    def init_stats_table(self):
        """Заполняем первый столбец таблицы статистики"""
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
        
        cat_name = self.table_category.item(row_index, 0).text()
        self.write_log(f"В статистику добавлен: {cat_name}")

    def save_stats(self):
        path = self.line_path_to_stats.text().strip()
        
        if not path:
            QMessageBox.warning(self, "Ошибка", "Введите путь для сохранения статистики!")
            return
            
        if not path.endswith('.xlsx'):
            path += '.xlsx'
            
        try:
            # ИЗМЕНЕНИЕ: Проверяем, существует ли файл
            if os.path.exists(path):
                # Если существует — загружаем его, чтобы обновить данные
                wb = openpyxl.load_workbook(path)
                ws = wb.active
                
                # Очищаем старые данные (строки со 2-й по 5-ю), чтобы записать новые
                for row in range(2, 6):
                    for col in range(1, 4):
                        ws.cell(row=row, column=col).value = None
            else:
                # Если файла нет — создаем новый
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "Статистика сортировки"
                
                headers = ["Категория", "Количество", "Время перемещения"]
                ws.append(headers)
                
                for cell in ws[1]:
                    cell.font = Font(bold=True)
                    
                ws.column_dimensions['A'].width = 15
                ws.column_dimensions['B'].width = 15
                ws.column_dimensions['C'].width = 25
            
            # Записываем актуальные данные из таблицы (в обоих случаях)
            for row in range(4):
                cat = self.table_category.item(row, 0).text()
                count = self.table_category.item(row, 1).text()
                time_str = self.table_category.item(row, 2).text()
                
                # Записываем начиная со 2-й строки (row+2)
                ws.cell(row=row+2, column=1).value = cat
                ws.cell(row=row+2, column=2).value = int(count)
                ws.cell(row=row+2, column=3).value = time_str
            
            wb.save(path)
            self.write_log(f"Статистика сохранена (обновлена) в Excel: {path}")
            QMessageBox.information(self, "Успех", f"Данные сохранены в файл:\n{path}")
            
        except Exception as e:
            self.write_log(f"Ошибка сохранения статистики: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить файл:\n{e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Arm165App()
    window.show()
    sys.exit(app.exec_())