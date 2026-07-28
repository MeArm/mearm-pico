import sys
import uselect
from machine import Pin, PWM, I2C
import time
import ssd1306  # Ensure ssd1306.py is saved on your Pico!
import random

# 1. Map physical GPIO pins
BASE_PIN     = 6
SHOULDER_PIN = 8
ELBOW_PIN    = 7
GRIPPER_PIN  = 9

# 2. SOFTWARE SAFETY LIMITS (Min Angle, Max Angle)
JOINT_LIMITS = [
    (1.0, 179.0),   # Base
    (35.0, 170.0),  # Shoulder
    (30.0, 130.0),  # Elbow
    (80.0, 170.0)   # Gripper
]

SERVO_NAMES = ["Base", "Shoulder", "Elbow", "Gripper"]

# 3. MOTION PROFILE CONFIGURATION
SMOOTHING_FACTORS = [0.08, 0.05, 0.12, 0.25]
TICK_INTERVAL_MS  = 20  
OLED_INTERVAL_MS  = 30  # 33Hz update clock for crisp, fast responsive animations

# Setup PWM frequencies for standard hobby servos (50Hz)
def init_servo(pin_num):
    pwm = PWM(Pin(pin_num))
    pwm.freq(50)
    return pwm

servos = [
    init_servo(BASE_PIN),
    init_servo(SHOULDER_PIN),
    init_servo(ELBOW_PIN),
    init_servo(GRIPPER_PIN)
]

# 4. OLED Display Setup (128x32 px on I2C1)
try:
    i2c = I2C(0, sda=Pin(12), scl=Pin(13), freq=400000)
    oled = ssd1306.SSD1306_I2C(128, 32, i2c)
    oled_active = True
    print("OLED Display initialized successfully.")
except Exception as e:
    print(f"OLED Initialization Failed: {e}. Running blind mode.")
    oled_active = False

# Track floating points for precise fractional-degree tracking
current_angles = [90.0, 90.0, 90.0, 40.0]  
target_angles  = [90.0, 90.0, 90.0, 40.0]
system_status  = "Ready"

# Animation & Idle State Variables
blink_timer = 0
is_blinking = False
last_movement_time = time.ticks_ms()
is_idle = False

# Random look-around variables
idle_look_timer = 0
idle_offset_x = 0
idle_offset_y = 0

# Convert 0-180 degrees into 16-bit duty cycle (1638 to 8192)
def set_angle(servo, angle):
    duty = int(1638 + (angle / 180) * (8192 - 1638))
    servo.duty_u16(duty)

# Initialize home positions safely within bounds immediately
for i in range(4):
    set_angle(servos[i], current_angles[i])

# Setup non-blocking serial read
spoll = uselect.poll()
spoll.register(sys.stdin, uselect.POLLIN)

last_tick_time = time.ticks_ms()
last_oled_time = time.ticks_ms()

print("Pico Advanced Motion Engine Active with Safety Boundaries.")
print("Send: base,shoulder,elbow,gripper")

# Draw Akno-style geometric tracking block eyes
def render_robot_eyes():
    if not oled_active:
        return
    oled.fill(0)
    
    global blink_timer, is_blinking, idle_look_timer, idle_offset_x, idle_offset_y
    
    # --- DYNAMIC TARGET TRACKING OR IDLE LOOK-AROUND ---
    if is_idle:
        # Increment timer to change look directions when sitting idle
        idle_look_timer += 1
        if idle_look_timer > 60:  # Pick a new direction roughly every 2 seconds
            idle_look_timer = 0
            # 30% chance to look back at center, 70% to look randomly
            if random.random() < 0.3:
                idle_offset_x = 0
                idle_offset_y = 0
            else:
                idle_offset_x = random.choice([-8, -4, 4, 8])
                idle_offset_y = random.choice([-4, 0, 4])
        
        offset_x = idle_offset_x
        offset_y = idle_offset_y
        gripper_delta = 0.0
    else:
        # Real-time mathematical error tracking vector calculations
        base_delta     = target_angles[0] - current_angles[0]
        vertical_delta = (target_angles[1] - current_angles[1]) + (target_angles[2] - current_angles[2])
        gripper_delta  = target_angles[3] - current_angles[3]
        
        # --- HIGH SENSITIVITY MULTIPLIER ---
        SENSITIVITY_X = 0.35
        SENSITIVITY_Y = 0.35
        
        # Calculate geometric shift constraints based on arm tracking errors
        offset_x = max(-10, min(10, int(base_delta * SENSITIVITY_X)))
        offset_y = max(-6, min(6, int(-vertical_delta * SENSITIVITY_Y)))
    
    # Global background ticking mechanisms for automatic blinking
    blink_timer += 1
    if blink_timer > 90:
        is_blinking = True
        if blink_timer > 93:
            is_blinking = False
            blink_timer = 0

    # Akno Base Geometry Specifications (Solid Blocks)
    EYE_W = 26
    EYE_H = 26
    EYE_Y = 3
    
    LEFT_X  = 24 + offset_x
    RIGHT_X = 78 + offset_x
    final_y = EYE_Y + offset_y

    # --- AKNO EXPRESSION LAYER ---
    if is_blinking:
        # Blink state: Drawn as simple crisp structural horizontal vectors
        oled.hline(LEFT_X, 16, EYE_W, 1)
        oled.hline(RIGHT_X, 16, EYE_W, 1)
    else:
        # Gripper Reaction Mode: Squashes height down to look "suspicious/focused"
        if abs(gripper_delta) > 1.0:
            EYE_H = 12
            final_y = 10 + offset_y

        # Draw the main solid filled block structures
        oled.fill_rect(LEFT_X, final_y, EYE_W, EYE_H, 1)
        oled.fill_rect(RIGHT_X, final_y, EYE_W, EYE_H, 1)
        
        # Limit Cap Mode: Modifies eye blocks with negative lines to slice an "Angry" shape
        if system_status == "LIMIT CAP!":
            # Mask out portions of the boxes to make angled geometric cuts
            for row in range(10):
                # Slice outer top corners moving downward diagonally
                oled.hline(LEFT_X, final_y + row, row + 1, 0)
                oled.hline(RIGHT_X + EYE_W - (row + 1), final_y + row, row + 1, 0)

    oled.show()

# Main Non-Blocking Loop
buffer = ""
while True:
    current_time = time.ticks_ms()

    # --- PART A: Non-Blocking Serial Read & Safety Validation ---
    if spoll.poll(0): 
        char = sys.stdin.read(1)
        if char == '\n' or char == '\r':
            if buffer:
                # Signal active connection: Reset idle status immediately on incoming data
                last_movement_time = current_time
                is_idle = False
                
                try:
                    angles = [float(x.strip()) for x in buffer.split(",")]
                    if len(angles) == 4:
                        
                        # --- Safety Bound Checker Loop ---
                        validated_angles = []
                        warning_triggered = False
                        for i in range(4):
                            min_limit, max_limit = JOINT_LIMITS[i]
                            raw_input = angles[i]
                            
                            # Check if the requested angle breaks safety boundaries
                            if raw_input < min_limit:
                                validated_angles.append(min_limit)
                                warning_triggered = True
                                print(f"⚠️ Warning: {SERVO_NAMES[i]} input ({raw_input}) too low! Capped at min limit: {min_limit}")
                            elif raw_input > max_limit:
                                validated_angles.append(max_limit)
                                warning_triggered = True
                                print(f"⚠️ Warning: {SERVO_NAMES[i]} input ({raw_input}) too high! Capped at max limit: {max_limit}")
                            else:
                                validated_angles.append(raw_input)
                        
                        if warning_triggered:
                            system_status = "LIMIT CAP!"
                        else:
                            system_status = "Moving"

                        # Update the target positions using the verified safe coordinates
                        target_angles = validated_angles
                    else:
                        print("Error: Must provide exactly 4 angles.")
                except ValueError:
                    print("Error: Invalid numbers.")
                buffer = "" 
        else:
            buffer += char

    # --- PART B: Independent Ramping Engine ---
    if time.ticks_diff(current_time, last_tick_time) >= TICK_INTERVAL_MS:
        last_tick_time = current_time
        
        all_reached = True
        for i in range(4):
            distance = target_angles[i] - current_angles[i]
            
            if abs(distance) < 0.1:
                current_angles[i] = target_angles[i]
            else:
                step = distance * SMOOTHING_FACTORS[i]
                current_angles[i] += step
                all_reached = False
            
            set_angle(servos[i], current_angles[i])
        
        # If moving, update the activity timer
        if not all_reached:
            last_movement_time = current_time
            is_idle = False
        else:
            # Clear limit cap alerts back to standard state once positioning finishes
            if system_status == "Moving" or system_status == "LIMIT CAP!":
                system_status = "Ready"
            
            # If completely stopped for 3000ms, trigger Idle Look-Around
            if time.ticks_diff(current_time, last_movement_time) > 3000:
                is_idle = True

    # --- PART C: Non-Blocking Animated Eye Refresh ---
    if time.ticks_diff(current_time, last_oled_time) >= OLED_INTERVAL_MS:
        last_oled_time = current_time
        render_robot_eyes()

    # Microsecond buffer to prevent CPU hogging
    time.sleep_us(100)
