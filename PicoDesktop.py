import tkinter as tk
from tkinter import ttk
import serial
import time

# Target Port: Replace 'COM3' (Windows) or '/dev/ttyACM0' (Mac/Linux) with your Pico's port
try:
    pico = serial.Serial('COM3', 115200, timeout=0.1)
    time.sleep(2) # Give connection brief window to settle
except Exception as e:
    print(f"Connection failed: {e}. Running in simulation mode.")
    pico = None

def send_command(servo_prefix, val):
    """Sends formatted angle commands to the Pico over USB serial"""
    angle = int(float(val))
    command = f"{servo_prefix}:{angle}\n"
    if pico and pico.is_open:
        pico.write(command.encode('utf-8'))
    else:
        print(f"Simulated Serial Tx: {command.strip()}")

# Setup Tkinter window
root = tk.Tk()
root.title("MeArm Control Center")
root.geometry("350x400")

# UI Layout Components
label = tk.Label(root, text="MeArm Robot Controller", font=("Arial", 14, "bold"))
label.pack(pady=10)

# Helper function to generate clean sliders
def create_slider(label_text, prefix, default_val):
    frame = tk.Frame(root)
    frame.pack(pady=10, fill='x', padx=20)
    
    lbl = tk.Label(frame, text=label_text, width=10, anchor='w')
    lbl.pack(side='left')
    
    slider = ttk.Scale(frame, from_=0, to=180, orient='horizontal',
                      command=lambda val: send_command(prefix, val))
    slider.set(default_val)
    slider.pack(side='right', expand=True, fill='x')

# Build sliders matching MeArm physical properties
create_slider("Base (Rotation)", "B", 90)
create_slider("Shoulder (Lift)", "S", 90)
create_slider("Elbow (Reach)", "E", 90)
create_slider("Claw (Grip)", "C", 90)

root.mainloop()

# Clean closing operations
if pico and pico.is_open:
    pico.close()