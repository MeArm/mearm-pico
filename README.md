# MeArm Pico 🤖 🎛️

A MicroPython and Python-based control suite for the **MeArm Robot Arm** powered by the **Raspberry Pi Pico**. This repository contains lightweight drivers, smooth movement controllers, and desktop GUI applications to orchestrate your robot arm seamlessly.

## 🚀 Features

*   **MicroPython Hardware Driver:** Optimized PWM control tailored specifically for the 4 degrees-of-freedom MeArm servos.
*   **Smooth Acceleration:** Built-in kinematic dampening (`smoothMeArm.py`) to reduce sudden jerky movements and prevent mechanical wear.
*   **Desktop Control Suites:** Cross-platform GUI scripts using `tkinter` to manipulate angles and paths directly from your laptop.
*   **Plug-and-Play USB Interface:** Serial-over-USB protocol (`PicoServoUSB.py`) for tethered automation.

---

## 📁 Repository Structure

**Pico firmware (MicroPython)**

*   `PicoServoUSB.py` - Listens on USB serial for `base,left,right,claw` lines (e.g. `90,120,45,100`). Needs `servo.py` on the Pico; an SSD1306 OLED (`ssd1306.py`) is optional.
*   `smoothMeArm.py` - Same serial protocol, but eases each servo smoothly towards its target.
*   `MeArmSolidEyes.py` - `smoothMeArm.py` plus animated "eyes" on a 128x32 SSD1306 OLED (I2C0, SDA GP12 / SCL GP13). Runs without the display if it isn't found.
*   `BasicPico.py` - Minimal firmware using a different protocol: one joint per line, e.g. `B:120`, `S:90`, `E:60`, `C:100`.

**Controllers (run on your computer)**

*   `pico_gui.py` - Tkinter sliders, record/replay and an arm diagram. Sends `base,left,right,claw` lines.
*   `DeskTopControl.py` - Tkinter sliders with smooth interpolated replay and a live Pico console. Sends `base,left,right,claw` lines.
*   `index.html` - Browser controller using Web Serial (Chrome/Edge). Sends `base,left,right,claw` lines.
*   `PicoDesktop.py` - Simple Tkinter sliders for `BasicPico.py` (`B:120` protocol). Edit the `COM3` port at the top of the file.
*   `tkExample.py` - Minimal example that shows serial output in a Tkinter window.

| Firmware | Works with |
| :--- | :--- |
| `PicoServoUSB.py`, `smoothMeArm.py`, `MeArmSolidEyes.py` | `pico_gui.py`, `DeskTopControl.py`, `index.html` |
| `BasicPico.py` | `PicoDesktop.py` |

---

## 🛠️ Hardware Setup

### Suggested Pinout Configuration
These are the pins used by the MeArm Pico board V1.0, and by every firmware script in this repo.

| MeArm Servo | Pico GPIO Pin | Software limits |
| :--- | :--- | :--- |
| **Base** | GPIO 6 | 1–179° |
| **Shoulder (Left)** | GPIO 7 | 35–170° |
| **Elbow (Right)** | GPIO 8 | 30–130° |
| **Claw (Grip)** | GPIO 9 | 80–170° |

The firmware clamps every command to these limits, and the desktop/web sliders use the same ranges. If you change them, change them in all the files.

> ⚠️ **Important:** Do not power the servo motors directly from the Pico’s 3.3V pin. Use an external 5V–6V (2A+) power supply. Ensure you connect the external power supply's ground (GND) to one of the Pico's GND pins to establish a common ground reference.

---

## 💻 Quick Start

### 1. Standalone Pico Control
1. Flash **MicroPython** onto your Raspberry Pi Pico.
2. Using an IDE like **Thonny**, open `smoothMeArm.py`.
3. Configure your GPIO pins inside the file if they differ from the defaults.
4. Run the file on your Pico. The arm moves to its home position and waits for commands. Type a line such as `90,120,45,100` into Thonny's shell to move it.

### 2. Desktop Slider App (USB Control) or MeArm Web Controller Pro
To orchestrate your MeArm using interactive sliders from your computer screen:

👉 **[Launch Live Web Controller](https://mearm.github.io/mearm-controller/)**

### OR

1. Upload `PicoServoUSB.py` to your Pico and name it `main.py` so it boots automatically.
2. Connect your Pico to your computer via a USB cable.
3. Install dependencies on your local machine:
   ```bash
   pip install pyserial
   ```
4. Run the GUI dashboard from your terminal:
   ```bash
   python pico_gui.py
   ```

---

## 📜 License

This project is open-source and licensed under the terms of the **MIT License**. See the `LICENSE` file for more details.
