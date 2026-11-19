#run on pi pico as main.py
#controls the servos for the MeArm Robot Arm without additional hardware
#requires servo.py and ssd1306.py to be saved on the Pico

from servo import Servo
from machine import Pin, I2C
import sys, select, time

# These are the attached servos on the MeArm Pico Board V1.0
servo_base  = Servo(pin=6)
servo_left  = Servo(pin=7)   # Shoulder
servo_right = Servo(pin=8)   # Elbow
servo_claw  = Servo(pin=9)

servos = [servo_base, servo_left, servo_right, servo_claw]
#set initital angles
angles = [ 90, 90, 90, 90]
# Software safety limits (min, max) - keep in sync with the desktop/web controllers
los    = [  1, 35, 30, 80]
his    = [179,170,130,170]

#using 180 degree servos, don't allow over value
def clamp(v, lo, hi):
    if v < lo: return lo
    if v > hi: return hi
    return v

# Move to initial position
for s, a in zip(servos, angles):
    s.move(a)

# Optional OLED display (128x32) - run without it if it isn't connected
try:
    from ssd1306 import SSD1306_I2C
    i2c = I2C(1, sda=Pin(10), scl=Pin(11), freq=400000)
    oled = SSD1306_I2C(128, 32, i2c)
except Exception as e:
    print("OLED not available:", e)
    oled = None

def show_status(a):
    if oled is None:
        return
    oled.fill(0)
    oled.text("MEARM STATUS", 0, 0)
    oled.text("B{} L{}".format(a[0], a[1]), 0, 12)
    oled.text("R{} C{}".format(a[2], a[3]), 0, 22)
    oled.show()

show_status(angles)

print("PICO READY")
print("Send: base,left,right,claw  e.g. 90,120,45,100")

poll = select.poll()
poll.register(sys.stdin, select.POLLIN)
buf = ""

while True:
    # Drain all available characters before doing anything else
    while poll.poll(0):
        ch = sys.stdin.read(1)
        if not ch:
            break
        if ch != "\n":
            if len(buf) < 64:
                buf += ch
            continue

        line = buf.strip()
        buf = ""
        if not line:
            continue

        try:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) != 4:
                print("ERR expected 4 comma separated values:", line)
                continue

            values = [float(p) for p in parts]
            if any(v != v for v in values):  # reject NaN
                raise ValueError("NaN not allowed")
            new_angles = [int(clamp(v, lo, hi)) for v, lo, hi in zip(values, los, his)]
            print("received", new_angles)

            if new_angles != angles:
                angles = new_angles
                for s, a in zip(servos, angles):
                    s.move(a)
                show_status(angles)
                print("OK", angles)

        except Exception as e:
            print("ERR", e, "line:", line)

    time.sleep(0.005)
