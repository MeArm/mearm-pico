import sys
import uselect
from machine import Pin, PWM

# Configure MeArm Servos on PWM pins
servos = {
    "B": PWM(Pin(0)),  # Base
    "S": PWM(Pin(1)),  # Shoulder
    "E": PWM(Pin(2)),  # Elbow
    "C": PWM(Pin(3))   # Claw
}

# Set frequency standard for 9g hobby servos (50Hz)
for servo in servos.values():
    servo.freq(50)

def set_angle(servo_id, angle):
    """Converts 0-180 degrees to Pico's 16-bit PWM duty cycle (approx 1638 to 8192)"""
    if servo_id in servos:
        angle = max(0, min(180, angle)) # Constrain limits
        # Duty cycle math for 50Hz: 0.5ms (0 deg) to 2.5ms (180 deg)
        duty = int(1638 + (angle / 180) * (8192 - 1638))
        servos[servo_id].duty_u16(duty)

# Set MeArm to a safe starting 'home' position
set_angle("B", 90)
set_angle("S", 90)
set_angle("E", 90)
set_angle("C", 90)

# Set up non-blocking serial input reader
spoll = uselect.poll()
spoll.register(sys.stdin, uselect.POLLIN)

buffer = ""
while True:
    if spoll.poll(10): # Check for incoming data
        char = sys.stdin.read(1)
        if char == "\n":
            # Process command format: "B:120" (Base to 120 degrees)
            if ":" in buffer:
                try:
                    part, angle_str = buffer.strip().split(":")
                    set_angle(part.upper(), int(angle_str))
                except ValueError:
                    pass
            buffer = ""
        else:
            buffer += char