import json
import queue
import serial
import serial.tools.list_ports
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# ----------------------------
# Helpers & Device Configurations
# ----------------------------
def list_serial_ports():
    return [(p.device, p.description) for p in serial.tools.list_ports.comports()]


def now_s():
    return time.time()


# MUST exactly match the safety limits programmed on your Pico
JOINT_LIMITS = [
    (1, 179),  # Base
    (35, 170),  # Left (Shoulder)
    (30, 130),  # Right (Elbow)
    (80, 170),  # Claw (Gripper)
]

JOINT_NAMES = ["Base", "Left", "Right", "Claw"]

# Home pose - every value must lie inside JOINT_LIMITS
HOME_POSITIONS = [90, 90, 90, 90]


def clamp_angle(idx, value):
    lo, hi = JOINT_LIMITS[idx]
    return max(lo, min(hi, int(value)))


def validate_points(pts):
    """Check a loaded recording; returns points sorted by time with angles clamped."""
    if not isinstance(pts, list) or not pts:
        raise ValueError("The selected JSON profile contains no points.")
    out = []
    for p in pts:
        if not isinstance(p, dict) or "t" not in p or "angles" not in p:
            raise ValueError("Each point needs a 't' and an 'angles' entry.")
        a = p["angles"]
        if not isinstance(a, list) or len(a) != 4:
            raise ValueError("Each point needs exactly 4 angles.")
        t = float(p["t"])
        if t != t or t < 0:
            raise ValueError("Bad time value.")
        out.append({"t": t, "angles": [clamp_angle(i, float(v)) for i, v in enumerate(a)]})
    out.sort(key=lambda p: p["t"])
    return out


class App:

    def __init__(self, root):
        self.root = root
        root.title("MeArm 4-Servo Advanced Controller")
        root.geometry("520x750")

        self.ser = None
        self.last_sent = None
        self.send_pending = False
        self.last_send_time = 0.0

        # Threading infrastructure for non-blocking serial reading
        self.serial_queue = queue.Queue()
        self.serial_thread = None
        self.is_running = True

        # Recording / playback
        self.is_recording = False
        self.record_start = 0.0
        self.recorded = []  # List of {"t": seconds, "angles": [...]}
        self.playing = False
        self.play_start_wall = 0.0
        self.play_speed = 1.0

        # UI variables
        self.port_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Not connected")

        # Initialize angles to a safe home position (inside JOINT_LIMITS)
        self.angle_vars = [tk.IntVar(value=v) for v in HOME_POSITIONS]

        self.build_ui()
        self.refresh_ports()

        # Start non-blocking tick loop (20ms interval = 50Hz)
        self.root.after(20, self.tick)

        # Handle window closure gracefully to clear active background threads
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------------- UI ----------------
    def build_ui(self):
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill="x")

        ttk.Label(top, text="Serial Port:").pack(side="left")
        self.port_combo = ttk.Combobox(
            top, textvariable=self.port_var, width=35, state="readonly"
        )
        self.port_combo.pack(side="left", padx=8)

        ttk.Button(top, text="🔄", width=3, command=self.refresh_ports).pack(
            side="left"
        )
        ttk.Button(top, text="Connect", command=self.connect).pack(
            side="left", padx=4
        )
        ttk.Button(top, text="Disconnect", command=self.disconnect).pack(
            side="left"
        )

        main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both", expand=True)

        left = ttk.Frame(main)
        left.pack(side="left", fill="both", expand=True)

        # Build dynamic sliders capped tightly within our JOINT_LIMITS parameters
        for i, name in enumerate(JOINT_NAMES):
            row = ttk.Frame(left)
            row.pack(fill="x", pady=6)

            ttk.Label(
                row, text=name, width=10, font=("Helvetica", 10, "bold")
            ).pack(side="left")

            min_val, max_val = JOINT_LIMITS[i]
            scale = ttk.Scale(
                row,
                from_=min_val,
                to=max_val,
                orient="horizontal",
                command=lambda _v, idx=i: self.on_slider(idx),
            )
            # store the widget before set(), which may fire on_slider()
            setattr(self, f"scale_{i}", scale)
            scale.set(self.angle_vars[i].get())
            scale.pack(side="left", fill="x", expand=True, padx=8)

            ttk.Label(row, textvariable=self.angle_vars[i], width=5, anchor="e").pack(
                side="left"
            )

        btns = ttk.Frame(left)
        btns.pack(fill="x", pady=12)

        ttk.Button(
            btns, text="Home Arm Defaults", command=self.home
        ).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(
            btns, text="Force Send Packet", command=self.send_once
        ).pack(side="left", expand=True, fill="x", padx=2)

        # Recording controls panel
        rec = ttk.LabelFrame(
            left, text="Automated Record & Smooth Replay Engine", padding=10
        )
        rec.pack(fill="x", pady=10)

        self.btn_start_rec = ttk.Button(
            rec, text="🔴 Start Recording", command=self.start_recording
        )
        self.btn_start_rec.grid(row=0, column=0, sticky="ew", padx=4, pady=4)

        self.btn_stop_rec = ttk.Button(
            rec, text="⏹️ Stop Recording", state="disabled", command=self.stop_recording
        )
        self.btn_stop_rec.grid(row=0, column=1, sticky="ew", padx=4, pady=4)

        self.btn_play = ttk.Button(
            rec, text="▶️ Playback Sequence", command=self.play
        )
        self.btn_play.grid(row=1, column=0, sticky="ew", padx=4, pady=4)

        self.btn_stop_play = ttk.Button(
            rec, text="⏸️ Stop Play", state="disabled", command=self.stop_play
        )
        self.btn_stop_play.grid(row=1, column=1, sticky="ew", padx=4, pady=4)

        ttk.Label(rec, text="Playback Engine Speed:").grid(
            row=2, column=0, sticky="w", padx=4, pady=6
        )
        self.speed_var = tk.DoubleVar(value=1.0)
        self.speed_scale = ttk.Scale(
            rec, from_=0.25, to=2.0, orient="horizontal", variable=self.speed_var
        )
        self.speed_scale.grid(row=2, column=1, sticky="ew", padx=4)

        ttk.Button(
            rec, text="💾 Save to JSON File...", command=self.save_recording
        ).grid(row=3, column=0, sticky="ew", padx=4, pady=4)
        ttk.Button(
            rec, text="📂 Load JSON Path...", command=self.load_recording
        ).grid(row=3, column=1, sticky="ew", padx=4, pady=4)

        rec.columnconfigure(0, weight=1)
        rec.columnconfigure(1, weight=1)

        # REAL-TIME EMBEDDED CONSOLE OUTPUT
        console_frame = ttk.LabelFrame(
            left, text="Live Pico Hardware Terminal Output", padding=5
        )
        console_frame.pack(fill="both", expand=True, pady=10)

        self.console_text = tk.Text(
            console_frame, height=8, wrap="word", font=("Courier", 9), bg="#1e1e1e", fg="#ffffff"
        )
        self.console_text.pack(side="left", fill="both", expand=True)

        console_scroll = ttk.Scrollbar(
            console_frame, orient="vertical", command=self.console_text.yview
        )
        console_scroll.pack(side="right", fill="y")
        self.console_text.config(yscrollcommand=console_scroll.set)

        bottom = ttk.Frame(self.root, padding=10, relief="sunken")
        bottom.pack(fill="x", side="bottom")
        ttk.Label(bottom, textvariable=self.status_var, font=("Courier", 9)).pack(
            side="left"
        )

    # ---------------- Communications Management ----------------
    def refresh_ports(self):
        ports = list_serial_ports()
        if not ports:
            self.port_combo["values"] = []
            self.port_var.set("")
            self.status_var.set("Status: Disconnected. No Pico USB devices found.")
            return

        values = [f"{dev} — {desc}" for dev, desc in ports]
        self.port_combo["values"] = values
        if not self.port_var.get():
            self.port_var.set(values[0])
        self.status_var.set("Status: Serial ports loaded. Click Connect.")

    def connect(self):
        if self.ser:
            return
        sel = self.port_var.get()
        if not sel:
            messagebox.showerror("Error", "Please select a serial communication port.")
            return
        port = sel.split(" — ")[0].strip()

        try:
            self.ser = serial.Serial(port, 115200, timeout=0.1)
            time.sleep(0.1)  # Brief delay to allow serial bus to stabilize
            self.status_var.set(f"Connected to {port} at 115200 Baud.")
            self.send_pending = True

            # Fire up background thread worker to monitor input
            self.is_running = True
            self.serial_thread = threading.Thread(
                target=self.read_serial_worker, args=(self.ser,), daemon=True
            )
            self.serial_thread.start()
            self.log_to_console("[System Client]: Connected to hardware device.\n")

        except Exception as e:
            self.ser = None
            messagebox.showerror("Connection Failed", f"Could not access port:\n{e}")

    def disconnect(self):
        self.stop_play()
        was_connected = self.ser is not None
        self.is_running = False  # Terminate reading worker loop
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
        self.ser = None
        if self.serial_thread and self.serial_thread is not threading.current_thread():
            self.serial_thread.join(timeout=0.5)
        self.serial_thread = None
        if not was_connected:
            return
        self.status_var.set("Status: Serial line disconnected.")
        self.log_to_console("[System Client]: Disconnected from hardware device.\n")

    def read_serial_worker(self, ser):
        """Asynchronous worker that watches incoming USB serial streams.

        Bound to the port it was started for, so a quick disconnect/reconnect
        can't leave an old worker reading the new port."""
        while self.is_running and ser is self.ser and ser.is_open:
            try:
                if ser.in_waiting > 0:
                    line = ser.readline().decode("utf-8", errors="ignore")
                    if line:
                        self.serial_queue.put(line)
            except Exception:
                break
            time.sleep(0.01)

    def log_to_console(self, text):
        """Safely appends string updates straight onto terminal interface."""
        self.console_text.insert(tk.END, text)
        self.console_text.see(tk.END)  # Focus auto-scroll down to bottom

    def send_angles(self, angles):
        if not self.ser or not self.ser.is_open:
            return
        line = f"{angles[0]},{angles[1]},{angles[2]},{angles[3]}\n"
        try:
            self.ser.write(line.encode("utf-8"))
        except Exception as e:
            self.status_var.set(f"Fatal Communication Drop: {e}")
            self.disconnect()
    # ---------------- Actions & Calculations ----------------
    def current_angles(self):
        return [v.get() for v in self.angle_vars]

    def on_slider(self, idx):
        scale = getattr(self, f"scale_{idx}")
        self.angle_vars[idx].set(int(float(scale.get())))
        self.send_pending = True
        if self.is_recording:
            self.record_point()

    def home(self):
        for i in range(4):
            getattr(self, f"scale_{i}").set(HOME_POSITIONS[i])
            self.angle_vars[i].set(HOME_POSITIONS[i])
        self.send_pending = True
        if self.is_recording:
            self.record_point()

    def send_once(self):
        self.send_pending = True
        self.last_sent = None

    # ---------------- Advanced Timeline Processing ----------------
    def start_recording(self):
        self.recorded = []
        self.is_recording = True
        self.record_start = now_s()
        self.btn_start_rec.config(state="disabled")
        self.btn_stop_rec.config(state="normal")
        self.status_var.set("Recording: Move sliders to cache paths...")
        self.record_point(force=True)

    def stop_recording(self):
        if self.is_recording:
            self.is_recording = False
            self.btn_start_rec.config(state="normal")
            self.btn_stop_rec.config(state="disabled")
            self.status_var.set(
                f"Saved cache sequence containing {len(self.recorded)} positional arrays."
            )

    def record_point(self, force=False):
        t = now_s() - self.record_start
        angles = self.current_angles()
        if force or (not self.recorded) or (self.recorded[-1]["angles"] != angles):
            self.recorded.append({"t": round(t, 3), "angles": angles[:]})

    def play(self):
        if not self.recorded:
            messagebox.showinfo(
                "Playback Alert",
                "The timeline cache is empty. Record or load a valid path.",
            )
            return
        if not self.ser:
            messagebox.showinfo(
                "Hardware Alert",
                "Establish an active serial link with the Pico first.",
            )
            return
        self.playing = True
        self.btn_play.config(state="disabled")
        self.btn_stop_play.config(state="normal")
        self.play_start_wall = now_s()
        self.status_var.set("Executing automated playback engine...")

    def stop_play(self):
        if self.playing:
            self.playing = False
            self.btn_play.config(state="normal")
            self.btn_stop_play.config(state="disabled")
            self.status_var.set("Playback pipeline manually halted.")

    def apply_angles_to_ui(self, angles):
        for i, val in enumerate(angles):
            clean_val = clamp_angle(i, val)
            getattr(self, f"scale_{i}").set(clean_val)
            self.angle_vars[i].set(clean_val)
        self.send_pending = True

    def save_recording(self):
        if not self.recorded:
            messagebox.showinfo(
                "File Error",
                "No data available within the current track space.",
            )
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("JSON Motion Profiles", "*.json")]
        )
        if not path:
            return
        data = {"limits": JOINT_LIMITS, "points": self.recorded}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        self.status_var.set(f"Successfully compiled tracking database: {path}")

    def load_recording(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON Motion Profiles", "*.json")]
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("The selected file is not a motion profile.")
            self.recorded = validate_points(data.get("points", []))
            self.status_var.set(
                f"Successfully buffered timeline: {len(self.recorded)} steps loaded."
            )
        except Exception as e:
            messagebox.showerror(
                "Import Blocked", f"Error parsing document structure:\n{e}"
            )

    # ---------------- Synchronous Tick Scheduler ----------------
    def tick(self):
        # Empty out accumulated serial lines from thread cache queue without lagging GUI
        while not self.serial_queue.empty():
            try:
                incoming_msg = self.serial_queue.get_nowait()
                self.log_to_console(incoming_msg)
            except queue.Empty:
                break

        try:
            self.play_speed = float(self.speed_var.get())
        except ValueError:
            self.play_speed = 1.0

        if self.playing and self.recorded and self.ser:
            elapsed_time = (now_s() - self.play_start_wall) * self.play_speed

            if elapsed_time >= self.recorded[-1]["t"]:
                self.apply_angles_to_ui(self.recorded[-1]["angles"])
                self.stop_play()
                self.status_var.set("Playback execution finalized safely.")
            else:
                p_start = self.recorded[0]
                p_end = self.recorded[-1]

                for idx in range(len(self.recorded) - 1):
                    if (
                        self.recorded[idx]["t"]
                        <= elapsed_time
                        <= self.recorded[idx + 1]["t"]
                    ):
                        p_start = self.recorded[idx]
                        p_end = self.recorded[idx + 1]
                        break

                time_span = p_end["t"] - p_start["t"]
                if time_span > 0:
                    factor = (elapsed_time - p_start["t"]) / time_span
                    interpolated_angles = []
                    for i in range(4):
                        a_start = p_start["angles"][i]
                        a_end = p_end["angles"][i]
                        current_frame_pos = (
                            a_start + (a_end - a_start) * factor
                        )
                        interpolated_angles.append(current_frame_pos)

                    self.apply_angles_to_ui(interpolated_angles)
                else:
                    self.apply_angles_to_ui(p_start["angles"])

        # Transmission rate limiter (Throttled tightly at 40ms intervals = ~25Hz)
        if self.ser and self.send_pending:
            t = now_s()
            if (t - self.last_send_time) > 0.04:
                angles = self.current_angles()
                if angles != self.last_sent or self.playing:
                    self.send_angles(angles)
                    self.last_sent = angles
                    self.last_send_time = t
                    if not self.playing and not self.is_recording:
                        self.status_var.set(f"Packet: {angles}")

        # Cycle loop callback
        self.root.after(20, self.tick)

    def on_close(self):
        """Fires when closing window to terminate background operations."""
        self.is_running = False
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except Exception:
                pass
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()

