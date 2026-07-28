#run on pi pico as main.py
#controls the servos for the MeArm Robot Arm without additional hardware

from servo import Servo
from machine import Pin, I2C, ADC, PWM
import sys, select, time
from ssd1306 import SSD1306_I2C

i2c=I2C(1,sda=Pin(10), scl=Pin(11), freq=400000)

# These are the attached servos on the MeArm Pico Board V1.0
servo_base  = Servo(pin=6)
servo_left  = Servo(pin=7)
servo_right = Servo(pin=8)
servo_claw  = Servo(pin=9)

servos = [servo_base, servo_left, servo_right, servo_claw]
#set initital angles
angles = [ 90, 90, 90, 90]
los    = [  0,  0,  0,  0]
his    = [180,180,180,180]

#using 180 degree servos, don't allow over value
def clamp(v, lo, hi):
    if v < lo: return lo
    if v > hi: return hi
    return v

# Move to initial position
for s, a in zip(servos, angles):
    s.move(a)

print("PICO READY")
print("Send: base,left,right,claw  e.g. 90,120,45,30")

poll = select.poll()
poll.register(sys.stdin, select.POLLIN)
buf = ""

# Define the display and size (128x32)
oled = SSD1306_I2C(128, 64, i2c)

# Clear the display first
oled.fill(0) 

while True:
    if poll.poll(0):
        ch = sys.stdin.read(1)
        if ch:
            if ch == "\n":
                line = buf.strip()
                buf = ""
                if not line:
                    continue

                try:
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) != 4:
                        print("ERR expected 4 comma seperated values:", line)
                        continue

                    new_angles = [clamp(int(p), los(p), his(p)) for p in parts]
                    print("received", new_angles)

                    if new_angles != angles:
                        angles = new_angles
                        for s, a in zip(servos, angles):
                            s.move(a)
                        print("OK", angles)

                except Exception as e:
                    print("ERR", e, "line:", line)
            else:
                buf += ch
                
    oled.fill(0) 
    oled.text("--- MEARM STATUS ---", 0, 0)
    oled.show()

    time.sleep(0.005)