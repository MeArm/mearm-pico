# MeArm Pico 🤖 🎛️

A MicroPython and Python-based control suite for the **MeArm Robot Arm** powered by the **Raspberry Pi Pico**. This repository contains lightweight drivers, smooth movement controllers, and desktop GUI applications to orchestrate your robot arm seamlessly.

## 🚀 Features

*   **MicroPython Hardware Driver:** Optimized PWM control tailored specifically for the 4 degrees-of-freedom MeArm servos.
*   **Smooth Acceleration:** Built-in kinematic dampening (`smoothMeArm.py`) to reduce sudden jerky movements and prevent mechanical wear.
*   **Desktop Control Suites:** Cross-platform GUI scripts using `tkinter` to manipulate angles and paths directly from your laptop.
*   **Plug-and-Play USB Interface:** Serial-over-USB protocol (`PicoServoUSB.py`) for tethered automation.

---

## 📁 Repository Structure

*   `BasicPico.py` - Core MicroPython script for standalone, automated joint movements on the Pico.
*   `smoothMeArm.py` - Advanced algorithm script designed to ramp servo speeds for fluid motion profiles.
*   `PicoServoUSB.py` - Establishes a listening serial interface on the Pico to accept coordinate inputs.
*   `pico_gui.py` / `DeskTopControl.py` / `PicoDesktop.py` - Interactive Tkinter-based desktop dashboards providing graphical sliders for the base, shoulder, elbow, and claw.
*   `MeArmSolidEyes.py` - Script supporting visual feedback components or auxiliary tracking.
*   `index.html` - Web-based framework documentation or integrated interface reference.

---

## 🛠️ Hardware Setup

### Suggested Pinout Configuration
Connect your 4 servo motors (Base, Left/Shoulder, Right/Elbow, Claw) to the Raspberry Pi Pico's PWM-capable GPIO pins. 

| MeArm Servo | Pico GPIO Pin |
| :--- | :--- |
| **Base** | GPIO 12 |
| **Shoulder (Left)** | GPIO 13 |
| **Elbow (Right)** | GPIO 14 |
| **Claw (Grip)** | GPIO 15 |

> ⚠️ **Important:** Do not power the servo motors directly from the Pico’s 3.3V pin. Use an external 5V–6V (2A+) power supply. Ensure you connect the external power supply's ground (GND) to one of the Pico's GND pins to establish a common ground reference.

---

## 💻 Quick Start

### 1. Standalone Pico Control
1. Flash **MicroPython** onto your Raspberry Pi Pico.
2. Using an IDE like **Thonny**, open `BasicPico.py` or `smoothMeArm.py`.
3. Configure your GPIO pins inside the file if they differ from the defaults.
4. Run the file on your Pico to watch the arm execute a pre-programmed diagnostic sequence.

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
