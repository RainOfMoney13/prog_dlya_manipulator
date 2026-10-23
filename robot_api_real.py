import time

class RobotARM165:
    def __init__(self, ip="192.168.1.100", port=8080):
        self.connected = False
        self.position = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0] # x, y, z, rx, ry, rz
    
    def connect(self):
        self.connected = True
        print("Робот подключен (Заглушка)")
        return True
    
    def move_to_point(self, x, y, z):
        if not self.connected: return False
        time.sleep(0.5) # Имитация движения
        self.position[0:3] = [x, y, z]
        print(f"Робот переместился в X:{x}, Y:{y}, Z:{z}")
        return True
    
    def gripper_on(self):
        print("Захват ВКЛ")
        return True
        
    def gripper_off(self):
        print("Захват ВЫКЛ")
        return True

    def get_position(self):
        return self.position