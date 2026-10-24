class RobotARM165:
    def __init__(self):
        self.connected = False
        self.position = {"x": 0.0, "y": 0.0, "z": 0.0}
        self.gripper_closed = False
        self.conveyor_on = False
        
    def connect(self):
        self.connected = True
        return True
    
    def move_to_start(self):
        self.position = {"x": 0.0, "y": 0.0, "z": 0.0}
        return True
        
    def toggle_gripper(self, state):
        self.gripper_closed = state
        return True
        
    def toggle_conveyor(self, state):
        self.conveyor_on = state
        return True
        
    def pause(self): return True
    def stop(self): return True
        
    def get_actual_pose(self):
        return [self.position["x"], self.position["y"], self.position["z"]]
        
    def get_motor_ticks(self):
        return [0, 0, 0, 0, 0, 0]