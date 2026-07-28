import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json, time, math
import serial
import serial.tools.list_ports

# ----------------------------
# Helpers
# ----------------------------
def list_serial_ports():
    return [(p.device, p.description) for p in serial.tools.list_ports.comports()]

def now_s():
    return time.time()

class App:
    def __init__(self, root):
        self.root = root
        root.title("MeArm 4-Servo Controller (USB Serial)")

        self.ser = None
        self.last_sent = None
        self.send_pending = False
        self.last_send_time = 0.0

        # Recording / playback
        self.is_recording = False
        self.record_start = 0.0
        self.recorded = []  # list of {"t": seconds_from_start, "angles":[...]}
        self.playing = False
        self.play_index = 0
        self.play_start_wall = 0.0
        self.play_speed = 1.0

        # UI vars
        self.port_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Not connected")

        self.angle_vars = [tk.IntVar(value=90) for _ in range(4)]
        self.names = ["Base", "Left", "Right", "Claw"]

        self.build_ui()
        self.refresh_ports()

        self.root.after(20, self.tick)

        # ---------------- UI ----------------
    def build_ui(self):
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill="x")

        ttk.Label(top, text="Serial Port:").pack(side="left")
        self.port_combo = ttk.Combobox(top, textvariable=self.port_var, width=50, state="readonly")
        self.port_combo.pack(side="left", padx=8)

        ttk.Button(top, text="Refresh", command=self.refresh_ports).pack(side="left")
        ttk.Button(top, text="Connect", command=self.connect).pack(side="left", padx=6)
        ttk.Button(top, text="Disconnect", command=self.disconnect).pack(side="left")

        main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both", expand=True)

        # Left: sliders + controls
        left = ttk.Frame(main)
        left.pack(side="left", fill="both", expand=True)

        for i, name in enumerate(self.names):
            row = ttk.Frame(left)
            row.pack(fill="x", pady=6)

            ttk.Label(row, text=name, width=8).pack(side="left")

            scale = ttk.Scale(
                row, from_=0, to=180, orient="horizontal",
                command=lambda _v, idx=i: self.on_slider(idx)
            )
            scale.set(90)
            scale.pack(side="left", fill="x", expand=True, padx=8)

            ttk.Label(row, textvariable=self.angle_vars[i], width=4).pack(side="left")

            # store scale widget for reading current values
            setattr(self, f"scale_{i}", scale)

        btns = ttk.Frame(left)
        btns.pack(fill="x", pady=8)

        ttk.Button(btns, text="Home (90s)", command=self.home).pack(side="left")
        ttk.Button(btns, text="Send Once", command=self.send_once).pack(side="left", padx=6)

          # Recording controls
        rec = ttk.LabelFrame(left, text="Record / Replay", padding=10)
        rec.pack(fill="x", pady=10)

        ttk.Button(rec, text="Start Recording", command=self.start_recording).grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        ttk.Button(rec, text="Stop Recording", command=self.stop_recording).grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        ttk.Button(rec, text="Play", command=self.play).grid(row=1, column=0, sticky="ew", padx=4, pady=4)
        ttk.Button(rec, text="Stop", command=self.stop_play).grid(row=1, column=1, sticky="ew", padx=4, pady=4)

        ttk.Label(rec, text="Speed:").grid(row=2, column=0, sticky="w", padx=4)
        self.speed_var = tk.DoubleVar(value=1.0)
        speed = ttk.Scale(rec, from_=0.25, to=2.0, orient="horizontal", command=self.on_speed)
        speed.set(1.0)
        speed.grid(row=2, column=1, sticky="ew", padx=4)

        ttk.Button(rec, text="Save Recording…", command=self.save_recording).grid(row=3, column=0, sticky="ew", padx=4, pady=4)
        ttk.Button(rec, text="Load Recording…", command=self.load_recording).grid(row=3, column=1, sticky="ew", padx=4, pady=4)

        rec.columnconfigure(0, weight=1)
        rec.columnconfigure(1, weight=1)

        # Status bar
        bottom = ttk.Frame(self.root, padding=10)
        bottom.pack(fill="x")
        ttk.Label(bottom, textvariable=self.status_var).pack(side="left")


         # ---------------- Serial ----------------
    def refresh_ports(self):
        ports = list_serial_ports()
        if not ports:
            self.port_combo["values"] = []
            self.port_var.set("")
            self.status_var.set("No serial ports found (plug in MeArm?)")
            return

        values = [f"{dev} — {desc}" for dev, desc in ports]
        self.port_combo["values"] = values
        if not self.port_var.get():
            self.port_var.set(values[0])

        self.status_var.set("Select the MeArm COM port and Connect")

    def connect(self):
        if self.ser:
            return
        sel = self.port_var.get()
        if not sel:
            messagebox.showerror("Connect", "No serial port selected.")
            return
        port = sel.split(" — ")[0].strip()

        try:
            self.ser = serial.Serial(port, 115200, timeout=0.05)
            time.sleep(0.2)
            self.status_var.set(f"Connected to {port} @115200")
            self.send_pending = True
        except Exception as e:
            self.ser = None
            messagebox.showerror("Connect failed", str(e))

    def disconnect(self):
        self.stop_play()
        if self.ser:
            try:
                self.ser.close()
            except:
                pass
        self.ser = None
        self.status_var.set("Disconnected")

    def send_angles(self, angles):
        if not self.ser:
            return
        line = "{},{},{},{}\n".format(*angles)
        try:
            self.ser.write(line.encode("utf-8"))
        except Exception as e:
            self.status_var.set(f"Send error: {e}")
            self.disconnect()
    # ---------------- Actions ----------------
    def current_angles(self):
        vals = [(v.get()) for v in self.angle_vars]
        return vals

    def on_slider(self, idx):
        # sync int var from scale float
        scale = getattr(self, f"scale_{idx}")
        self.angle_vars[idx].set(int(float(scale.get())))
        self.send_pending = True
        self.redraw_diagram()
        if self.is_recording:
            self.record_point()

    def on_speed(self, _v):
        self.play_speed = float(self.speed_var.get())
        # ttk.Scale doesn't auto-bind var nicely; read from widget instead
        # We'll just set from widget every tick too.

    def home(self):
        for i in range(4):
            getattr(self, f"scale_{i}").set(90)
            self.angle_vars[i].set(90)
        self.send_pending = True
        self.redraw_diagram()
        if self.is_recording:
            self.record_point()

    def send_once(self):
        self.send_pending = True
        self.last_sent = None  # force send on next tick

    # ---------------- Recording ----------------
    def start_recording(self):
        self.recorded = []
        self.is_recording = True
        self.record_start = now_s()
        self.status_var.set("Recording… move sliders")
        self.record_point(force=True)

    def stop_recording(self):
        if self.is_recording:
            self.is_recording = False
            self.status_var.set(f"Recording stopped. {len(self.recorded)} points.")

    def record_point(self, force=False):
        # store only when angles change (or forced)
        t = now_s() - self.record_start
        angles = self.current_angles()
        if force or (not self.recorded) or (self.recorded[-1]["angles"] != angles):
            self.recorded.append({"t": round(t, 3), "angles": angles[:]})

    def play(self):
        if not self.recorded:
            messagebox.showinfo("Play", "No recording to play.")
            return
        if not self.ser:
            messagebox.showinfo("Play", "Connect to the Pico first.")
            return

        self.playing = True
        self.play_index = 0
        self.play_start_wall = now_s()
        self.status_var.set("Playing…")
        # apply first point immediately
        self.apply_angles_to_ui(self.recorded[0]["angles"], send=True)

    def stop_play(self):
        if self.playing:
            self.playing = False
            self.status_var.set("Playback stopped")

    def apply_angles_to_ui(self, angles, send=False):
        for i, a in enumerate(angles):
            getattr(self, f"scale_{i}").set(a)
            self.angle_vars[i].set(a)
        self.redraw_diagram()
        if send:
            self.send_pending = True
            self.last_sent = None

    def save_recording(self):
        if not self.recorded:
            messagebox.showinfo("Save", "Nothing recorded yet.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not path:
            return
        data = {
            "version": 1,
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "points": self.recorded
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        self.status_var.set(f"Saved recording: {path}")

    def load_recording(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            pts = data.get("points", [])
            if not pts:
                raise ValueError("No points found.")
            # basic validation
            for p in pts:
                if "t" not in p or "angles" not in p or len(p["angles"]) != 4:
                    raise ValueError("Bad format.")
            self.recorded = pts
            self.status_var.set(f"Loaded recording: {len(self.recorded)} points")
        except Exception as e:
            messagebox.showerror("Load failed", str(e))
            
# ---------------- Main loop tick ----------------
    def tick(self):
        # Keep play_speed synced from the scale widget
        # (ttk.Scale doesn't always keep the var in sync)
        # We'll find the speed scale by searching children once:
        # For simplicity, just read the var (works in most cases).
        try:
            self.play_speed = float(self.speed_var.get())
        except:
            self.play_speed = 1.0

        # Playback scheduling
        if self.playing and self.recorded and self.ser:
            elapsed_wall = now_s() - self.play_start_wall
            elapsed_play = elapsed_wall * self.play_speed

            # advance while next point is due
            while self.play_index + 1 < len(self.recorded) and self.recorded[self.play_index + 1]["t"] <= elapsed_play:
                self.play_index += 1
                self.apply_angles_to_ui(self.recorded[self.play_index]["angles"], send=True)

            # stop at end
            if self.play_index >= len(self.recorded) - 1:
                self.playing = False
                self.status_var.set("Playback finished")

        # Send to Pico at a reasonable rate
        if self.ser and self.send_pending:
            t = now_s()
            if (t - self.last_send_time) > 0.04:  # ~25 Hz
                angles = self.current_angles()
                if angles != self.last_sent:
                    self.send_angles(angles)
                    self.last_sent = angles
                    self.last_send_time = t
                    # keep status short while recording/playing
                    if self.playing:
                        pass
                    elif self.is_recording:
                        self.status_var.set(f"Recording… ({len(self.recorded)} pts)")
                    else:
                        self.status_var.set(f"Sent: {tuple(angles)}")

        self.root.after(20, self.tick)


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()