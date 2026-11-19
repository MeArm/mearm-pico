#Basic Firmware for the MeArm Pico
#This code, while being short contains some great features
#First it reads serial data in a "non blocking" way, checking for a command but moving on if its not there
#Second it moves the servos from point A to point B in a smooth way, closing a fixed fraction of the gap each tick (exponential easing)
#This also moves each servo sequentially in a micro step which helps with power consumption and avoids spikes 

import sys
import uselect
from machine import Pin, PWM
import time

# 1. Map physical GPIO pins
BASE_PIN     = 6
SHOULDER_PIN = 7
ELBOW_PIN    = 8
GRIPPER_PIN  = 9

# 2. SOFTWARE SAFETY LIMITS (Min Angle, Max Angle)
# Customize these numbers based on your robot's physical constraints!
JOINT_LIMITS = [
    (1.0, 179.0),  # Base: Prevent twisting wires or hitting base structure
    (35.0, 170.0),  # Shoulder: Prevent overloading/crashing into the table
    (30.0, 130.0),  # Elbow: Prevent hyper-extending the joint
    (80.0, 170.0)   # Gripper: Prevent crushing the servo when fully closed
]

# Names matching the order of limits for terminal printouts
SERVO_NAMES = ["Base", "Shoulder", "Elbow", "Gripper"]

# 3. MOTION PROFILE CONFIGURATION (Interpolation speeds)
SMOOTHING_FACTORS = [0.08, 0.05, 0.12, 0.25] # These give different joints different smoothing factors
TICK_INTERVAL_MS  = 20  

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

# Track floating points for precise fractional-degree tracking
current_angles = [90.0, 90.0, 90.0, 90.0]  
target_angles  = [90.0, 90.0, 90.0, 90.0]

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

print("Pico Advanced Motion Engine Active with Safety Boundaries.")
print("Send: base,shoulder,elbow,gripper")

# 4. Main Non-Blocking Loop
buffer = ""
while True:
    current_time = time.ticks_ms()

    # --- PART A: Non-Blocking Serial Read & Safety Validation ---
    if spoll.poll(0): 
        char = sys.stdin.read(1)
        if char == '\n' or char == '\r':
            if buffer:
                try:
                    angles = [float(x.strip()) for x in buffer.split(",")]
                    if any(a != a for a in angles):  # NaN would crash set_angle()
                        raise ValueError("NaN")
                    if len(angles) == 4:
                        
                        # --- Safety Bound Checker Loop ---
                        validated_angles = []
                        for i in range(4):
                            min_limit, max_limit = JOINT_LIMITS[i]
                            raw_input = angles[i]
                            
                            # Check if the requested angle breaks safety boundaries
                            if raw_input < min_limit:
                                validated_angles.append(min_limit)
                                print(f"⚠️ Warning: {SERVO_NAMES[i]} input ({raw_input}) too low! Capped at min limit: {min_limit}")
                            elif raw_input > max_limit:
                                validated_angles.append(max_limit)
                                print(f"⚠️ Warning: {SERVO_NAMES[i]} input ({raw_input}) too high! Capped at max limit: {max_limit}")
                            else:
                                validated_angles.append(raw_input)
                        
                        # Update the target positions using the verified safe coordinates
                        target_angles = validated_angles
                        print(f"New targets buffered: {target_angles}")
                    else:
                        print("Error: Must provide exactly 4 angles.")
                except ValueError:
                    print("Error: Invalid numbers.")
                buffer = "" 
        elif len(buffer) < 64:  # cap length so line noise can't exhaust RAM
            buffer += char

    # --- PART B: Independent Ramping Engine ---
    if time.ticks_diff(current_time, last_tick_time) >= TICK_INTERVAL_MS:
        last_tick_time = current_time
        
        for i in range(4):
            distance = target_angles[i] - current_angles[i]
            
            if abs(distance) < 0.1:
                current_angles[i] = target_angles[i]
            else:
                step = distance * SMOOTHING_FACTORS[i]
                current_angles[i] += step
            
            set_angle(servos[i], current_angles[i])

    # Microsecond buffer to prevent CPU hogging
    time.sleep_us(100)