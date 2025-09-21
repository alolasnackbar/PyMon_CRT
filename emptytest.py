# monitor_core.py ========================================================
import psutil
import subprocess
import platform
import time
import shutil
import re
import os
import sys
from datetime import datetime

# ---- Optional Windows WMI ----
WMI_AVAILABLE = False
if platform.system() == "Windows":
    try:
        import wmi  # type: ignore
        WMI_AVAILABLE = True
    except ImportError:
        print("WMI library not found. For better CPU info on Windows, run: pip install wmi")
        WMI_AVAILABLE = False

# ---- Helpers ----
def _which(cmd: str) -> bool:
    """Check if a command is available in the system's PATH."""
    return shutil.which(cmd) is not None

def _run_cmd(args, timeout=0.3):
    """Run a subprocess command and return its output."""
    try:
        # For Windows, prevent a console window from appearing
        startupinfo = None
        if platform.system() == "Windows":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        out = subprocess.check_output(
            args, stderr=subprocess.DEVNULL, timeout=timeout, text=True, startupinfo=startupinfo
        )
        return out.strip()
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return None

# ---- CPU ----
def get_cpu_usage(interval=None):
    """Return CPU usage percent."""
    try:
        return psutil.cpu_percent(interval=interval)
    except Exception:
        return 0.0

_last_freq_check = 0
_last_freq_tuple = None
def get_cpu_freq(rate_limit_sec: float = 2.0):
    """Returns a tuple (current_GHz, min_GHz, max_GHz), rate-limited."""
    global _last_freq_check, _last_freq_tuple
    now = time.time()
    if (now - _last_freq_check) < rate_limit_sec and _last_freq_tuple:
        return _last_freq_tuple
    try:
        f = psutil.cpu_freq(percpu=False)
        if f:
            _last_freq_tuple = (
                round(f.current / 1000.0, 2),
                round(f.min / 1000.0, 2) if f.min else 0,
                round(f.max / 1000.0, 2) if f.max else 0,
            )
            _last_freq_check = now
            return _last_freq_tuple
    except Exception:
        return None
    return None

_cpu_model_cache = None
def get_cpu_info():
    """Returns a dictionary with CPU model and core counts."""
    global _cpu_model_cache
    if _cpu_model_cache is None:
        model = "Unknown CPU"
        try:
            system = platform.system()
            if system == "Windows" and WMI_AVAILABLE:
                c = wmi.WMI()
                for processor in c.Win32_Processor():
                    model = processor.Name
            elif system == "Linux":
                with open("/proc/cpuinfo") as f:
                    for line in f:
                        if "model name" in line:
                            model = line.split(":", 1)[1].strip()
                            break
            else: # Fallback for other OS or if above fails
                model = platform.processor()
        except Exception:
             model = platform.processor()
        _cpu_model_cache = {"model": model, "physical_cores": psutil.cpu_count(logical=False), "logical_cores": psutil.cpu_count(logical=True)}
    return _cpu_model_cache

def get_cpu_temp():
    """Returns CPU temperature in Celsius, or None if not available."""
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            for name, entries in temps.items():
                if "core" in name.lower() or "cpu" in name.lower() or "package" in name.lower():
                    for entry in entries:
                        return entry.current
    except Exception:
        pass
    if platform.system() == "Windows" and WMI_AVAILABLE:
        try:
            w = wmi.WMI(namespace="root\\wmi")
            temp_info = w.MSAcpi_ThermalZoneTemperature()
            if temp_info:
                return (temp_info[0].CurrentTemperature / 10.0) - 273.15
        except Exception:
            pass
    return None

def get_top_processes(limit=5):
    """Return top processes sorted by CPU usage."""
    procs = [p for p in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_info']) if p.info['cpu_percent'] is not None]
    procs.sort(key=lambda p: p.info['cpu_percent'], reverse=True)
    
    top_procs = []
    for p in procs[:limit]:
        try:
            virt = p.info['memory_info'].vms / (1024 * 1024)
            res = p.info['memory_info'].rss / (1024 * 1024)
            top_procs.append(
                f"{p.info['pid']:<6} {str(p.info['username'])[:8]:<8} {virt:>6.1f}M {res:>6.1f}M "
                f"{p.info['cpu_percent']:>5.1f} {psutil.virtual_memory().percent:>5.1f}  {p.info['name']}"
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return top_procs

# ---- RAM ----
def get_ram_info():
    """Returns a dictionary of RAM usage details in GB."""
    try:
        mem = psutil.virtual_memory()
        return {"used": round(mem.used / (1024**3), 2), "available": round(mem.available / (1024**3), 2)}
    except Exception:
        return {"used": 0.0, "available": 0.0}

# ---- Disk ----
_last_disk_io = psutil.disk_io_counters()
_last_disk_ts = time.time()
def get_disk_io():
    """Returns (read_MB_per_s, write_MB_per_s) using a non-blocking method."""
    global _last_disk_io, _last_disk_ts
    now = time.time()
    io_now = psutil.disk_io_counters()
    elapsed = max(1e-6, now - _last_disk_ts)
    
    read_mb_s = (io_now.read_bytes - _last_disk_io.read_bytes) / (1024**2) / elapsed
    write_mb_s = (io_now.write_bytes - _last_disk_io.write_bytes) / (1024**2) / elapsed
    
    _last_disk_io = io_now
    _last_disk_ts = now
    return read_mb_s, write_mb_s

def get_disk_summary(max_drives=3):
    """Returns a formatted string of disk usage."""
    summary = []
    partitions = [p for p in psutil.disk_partitions() if 'cdrom' not in p.opts and p.fstype]
    for part in partitions[:max_drives]:
        try:
            usage = psutil.disk_usage(part.mountpoint)
            drive = part.device.replace('\\', '').replace('.', '')
            summary.append(f"{drive} {round(usage.used / (1024**3), 1)}/{round(usage.total / (1024**3), 1)} GB")
        except (PermissionError, FileNotFoundError):
            continue
    return " | ".join(summary)

# ---- GPU ----
def get_gpu_usage():
    """Returns GPU utilization percent, NVIDIA-only for now."""
    if _which("nvidia-smi"):
        out = _run_cmd(["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"])
        return float(out.strip()) if out else None
    return None

def get_gpu_temp():
    """Returns GPU temperature in Celsius, NVIDIA-only for now."""
    if _which("nvidia-smi"):
        out = _run_cmd(["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"])
        return float(out.strip()) if out else None
    return None

def get_gpu_info():
    """Returns GPU model name."""
    if _which("nvidia-smi"):
        return _run_cmd(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"])
    if platform.system() == "Windows" and WMI_AVAILABLE:
        try:
            w = wmi.WMI()
            gpus = [gpu.Name for gpu in w.Win32_VideoController()]
            return " / ".join(gpus) if gpus else None
        except Exception:
            pass
    return "N/A"

# ---- Time & Uptime ----
def get_local_time():
    """Return the current local time."""
    return datetime.now().strftime("%H:%M:%S %p")

def get_uptime():
    """Return system uptime in a human-readable format."""
    uptime_seconds = time.time() - psutil.boot_time()
    days, rem = divmod(uptime_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    return f"{int(days)}d {int(hours)}h {int(minutes)}m"

# ---- Network ----
_last_net_io = psutil.net_io_counters()
_last_net_ts = time.time()
def get_network_io():
    """Returns (download_MB_per_s, upload_MB_per_s) using a non-blocking method."""
    global _last_net_io, _last_net_ts
    now = time.time()
    io_now = psutil.net_io_counters()
    elapsed = max(1e-6, now - _last_net_ts)

    down_mb_s = (io_now.bytes_recv - _last_net_io.bytes_recv) / (1024**2) / elapsed
    up_mb_s = (io_now.bytes_sent - _last_net_io.bytes_sent) / (1024**2) / elapsed

    _last_net_io = io_now
    _last_net_ts = now
    return down_mb_s, up_mb_s

def get_latency(host="8.8.8.8", count=2, timeout=1):
    """Pings a host and returns the average latency in ms."""
    param = "-n" if platform.system() == "Windows" else "-c"
    try:
        output = _run_cmd(["ping", param, str(count), host], timeout=timeout)
        if output:
            if platform.system() == "Windows":
                match = re.search(r"Average = (\d+)", output)
                return float(match.group(1)) if match else None
            else:
                match = re.search(r"min/avg/max/mdev = [\d.]+/([\d.]+)/", output)
                return float(match.group(1)) if match else None
    except Exception:
        return None
    return None


# gui.py =======================================================================================
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import threading
import queue
from screeninfo import get_monitors
import os
import sys
import subprocess

# Assuming these files exist in the same directory
from constants import *
from crt_graphics import CRTGrapher, ThreadedDataFetcher
from metrics_layout import build_metrics
from startup_loader import startup_loader
import monitor_core as core

# --- Refresh Tiers ---
REFRESH_GUI_MS = 100
REFRESH_HEAVY_MS = 1500  # More intensive stats, less frequent
REFRESH_SLOW_MS = 5000   # Network latency, can be slow

# --- Global Settings ---
network_results = {"latency_ms": None}
data_queue = queue.Queue()

# --- Functions ---
def get_startup_monitor(script_dir):
    """Reads the selected monitor index from the config file."""
    config_path = os.path.join(script_dir, "startup_config.txt")
    try:
        with open(config_path, "r") as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return 0  # Default to primary monitor

def open_startup_settings(root):
    """Closes the current GUI and re-runs the startup settings script."""
    root.destroy()
    try:
        # Ensure we run the script from its directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        startup_script_path = os.path.join(script_dir, "startup_set.py")
        subprocess.run([sys.executable, startup_script_path], check=True)
    except Exception as e:
        print(f"Error opening startup settings: {e}")
        
def main():
    """Creates and runs the main application GUI."""
    root = tb.Window(themename="darkly")
    root.title("AlohaSnackBar Hardware Monitor")
    
    fullscreen = False
    script_dir = os.path.dirname(os.path.abspath(__file__))
    monitor_idx = get_startup_monitor(script_dir)
    
    try:
        monitors = get_monitors()
        if 0 < monitor_idx <= len(monitors):
            monitor = monitors[monitor_idx - 1]
            if monitor.width <= 1024 and monitor.height <= 768: # Adjusted for common small resolutions
                root.geometry(f"{monitor.width}x{monitor.height}+{monitor.x}+{monitor.y}")
                root.overrideredirect(True)
                fullscreen = True
            else:
                root.geometry(f"960x600+{monitor.x + 100}+{monitor.y + 100}")
        else:
            root.geometry("960x600")
    except Exception:
        root.geometry("960x600")

    # --- Grid Configuration ---
    root.rowconfigure(0, weight=1)
    root.rowconfigure(1, weight=1)
    root.rowconfigure(2, weight=1)
    root.columnconfigure(0, weight=1)
    root.columnconfigure(1, weight=1)
    style = tb.Style()

    # --- Menu Bar ---
    main_menu = tb.Menu(root)
    root.config(menu=main_menu)
    file_menu = tb.Menu(main_menu, tearoff=0)
    main_menu.add_cascade(label="File", menu=file_menu)
    file_menu.add_command(label="Exit", command=root.quit)
    control_menu = tb.Menu(main_menu, tearoff=0)
    main_menu.add_cascade(label="Settings", menu=control_menu)
    control_menu.add_command(label="Startup Settings", command=lambda: open_startup_settings(root))

    # --- Build Widgets ---
    widgets = build_metrics(root, style)
    
    # --- Graphics Initializer ---
    disk_io_widgets = widgets["Disk I/O"]
    crt_grapher = CRTGrapher(
        canvas=widgets["CPU"][2], io_canvas=disk_io_widgets[4], max_io=DISK_IO_MAX_MBPS,
        style=style, io_read_bar=disk_io_widgets[2], io_write_bar=disk_io_widgets[3],
        io_read_lbl=disk_io_widgets[0], io_write_lbl=disk_io_widgets[1]
    )

    # --- Helper Functions ---
    def get_temp_color(value):
        if value is None: return "success"
        if value < 75: return "success"
        elif value < 90: return "warning"
        else: return "danger"

    def get_usage_color(value):
        if value is None: return CRT_GREEN
        if value < 60: return CRT_GREEN
        elif value < 80: return CRT_YELLOW
        else: return CRT_RED

    # --- Fullscreen Toggling ---
    def toggle_fullscreen_handler(event=None):
        nonlocal fullscreen
        fullscreen = not fullscreen
        root.overrideredirect(fullscreen)
    root.bind("<F11>", toggle_fullscreen_handler)
    root.bind("<Escape>", toggle_fullscreen_handler)

    # --- GUI Update Loops ---
    def update_gui():
        try:
            history = data_queue.get_nowait()
            crt_grapher.frame_count += 3
            
            # Update primary metrics (CPU, RAM, GPU)
            for key in ["CPU", "RAM", "GPU"]:
                val = history.get(key, [None])[-1]
                if val is not None:
                    lbl, bar, cvs, maxv, overlay_lbl = widgets[key]
                    lbl_color = get_usage_color(val)
                    if key == "CPU":
                        freq = core.get_cpu_freq()
                        freq_text = f"{freq[0]:.2f} GHz" if freq else "N/A"
                        lbl.config(foreground=lbl_color, text=f"CPU Usage: {val:>5.1f}%   Speed: {freq_text}")
                    elif key == "RAM":
                        info = core.get_ram_info()
                        lbl.config(text=f"RAM Used: {info['used']:.2f} GB / Free: {info['available']:.2f} GB", foreground=lbl_color)
                        if overlay_lbl:
                            overlay_lbl.config(text=f"{val:.1f}%", background=lbl_color)
                    else: # GPU
                        lbl.config(foreground=lbl_color, text=f"{key} Usage: {val:>5.1f}%")
                    
                    style.configure(bar._style_name, background=lbl_color)
                    bar["value"] = val
                    crt_grapher.draw_metric(cvs, history[key], maxv, color=lbl_color)
            
            # Update Disk I/O
            read, write = history.get("DISK_read", [0])[-1], history.get("DISK_write", [0])[-1]
            crt_grapher.update_dual_io_labels(read, write)
            crt_grapher.draw_dual_io(history.get("DISK_read", []), history.get("DISK_write", []))

        except queue.Empty:
            pass
        finally:
            root.after(REFRESH_GUI_MS, update_gui)

    def update_heavy_stats():
        def worker():
            cpu_info = core.get_cpu_info()
            gpu_info = core.get_gpu_info()
            disk_use = core.get_disk_summary()
            cpu_temp = core.get_cpu_temp()
            gpu_temp = core.get_gpu_temp()
            load_avg = core.get_load_average()
            uptime = core.get_uptime()
            procs = core.get_top_processes(limit=5)
            net_down, net_up = core.get_network_io()
            top_text = "PID      USER     VIRT      RES      CPU%   MEM%   NAME\n" + "\n".join(procs)
            
            def apply_updates():
                # Sys Info Tab
                info_labels = widgets["Sys Info"]
                info_labels["CPU Model"].config(text=f"CPU: {cpu_info.get('model', 'N/A')}")
                info_labels["Cores"].config(text=f"Cores: {cpu_info.get('physical_cores', 'N/A')} | Threads: {cpu_info.get('logical_cores', 'N/A')}")
                info_labels["GPU"].config(text=f"GPU: {gpu_info}")
                info_labels["DISK"].config(text=f"Disk Usage: {disk_use}")
                info_labels["Net IN"].config(text=f"Download: {net_down:.2f} MB/s")
                info_labels["Net OUT"].config(text=f"Upload: {net_up:.2f} MB/s")
                lat = network_results['latency_ms']
                info_labels["Latency"].config(text=f"Latency: {lat:.1f} ms" if lat is not None else "Latency: N/A")
                
                # Processing Stats Tab
                cpu_labels = widgets["CPU Stats"]
                cpu_labels["Info"].config(text=f"Load Avg: {load_avg}    Uptime: {uptime}")
                cpu_labels["Top Processes"].config(text=top_text)

                # Temp Stats Tab
                if "Temp Stats" in widgets:
                    temp_widgets = widgets["Temp Stats"]
                    if "CPU Meter" in temp_widgets:
                        meter = temp_widgets["CPU Meter"]
                        if cpu_temp is not None:
                            meter.configure(amountused=cpu_temp, subtext=f"{cpu_temp:.1f}°C", bootstyle=get_temp_color(cpu_temp))
                        else:
                            meter.configure(amountused=0, subtext="N/A", bootstyle="default")
                    if "GPU Meter" in temp_widgets:
                        meter = temp_widgets["GPU Meter"]
                        if gpu_temp is not None:
                            meter.configure(amountused=gpu_temp, subtext=f"{gpu_temp:.1f}°C", bootstyle=get_temp_color(gpu_temp))
                        else:
                            meter.configure(amountused=0, subtext="N/A", bootstyle="default")
            
            root.after(0, apply_updates)
            root.after(REFRESH_HEAVY_MS, update_heavy_stats)
        
        threading.Thread(target=worker, daemon=True).start()

    def update_latency_stats():
        def worker():
            network_results["latency_ms"] = core.get_latency()
            root.after(REFRESH_SLOW_MS, update_latency_stats)
        threading.Thread(target=worker, daemon=True).start()

    def update_time():
        date_lbl, time_lbl = widgets["Time & Uptime"]
        time_lbl.config(text=core.get_local_time())
        # The date only needs to be set once, but this is fine.
        date_lbl.config(text=datetime.now().strftime("%a, %b %d, %Y"))
        root.after(1000, update_time)

    # --- Start All Processes ---
    def start_app():
        data_fetcher = ThreadedDataFetcher(data_queue, interval=REFRESH_MS / 1000)
        data_fetcher.start()
        update_gui()
        update_heavy_stats()
        update_latency_stats()
        update_time()

    startup_loader(root, widgets, style, on_complete=start_app)
    root.mainloop()

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)  # Set the current working directory
    
    config_file = "startup_config.txt"
    
    # Run the setup script ONLY if the config file doesn't exist.
    if not os.path.exists(config_file):
        print("First launch: running startup setup...")
        try:
            # Use pythonw to prevent a console window for the setup script
            py_executable = 'pythonw' if sys.platform == 'win32' else sys.executable
            subprocess.run([py_executable, "startup_set.py"], check=True)
            
            # If the user closed the setup window without saving, exit the main app.
            if not os.path.exists(config_file):
                sys.exit("Setup was not completed. Exiting.")
        except Exception as e:
            print(f"Could not run or complete startup_set.py: {e}")
            sys.exit(1)
            
    # If we get here, the config exists, so we can launch the main app.
    main()

#crt_graphics.py =================================================================
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import threading
import queue
import time
from constants import CRT_GREEN, CRT_GRID, MAX_POINTS, CRT_LINE_SMOT, FONT_TITLE, GRAPH_HEIGHT

# Import monitor_core directly. The mocking is for standalone testing.
try:
    import monitor_core as core
except ImportError:
    print("WARNING: 'monitor_core.py' not found. Using mock data for graphics.")
    class MockMonitorCore:
        def get_cpu_usage(self, interval=None): return 50.0
        def get_ram_usage(self): return 35.0
        def get_gpu_usage(self): return 20.0
        def get_disk_io(self): return 15.0, 7.0
        def get_network_io(self): return 5.0, 1.0
    core = MockMonitorCore()


# This class runs in a separate thread to collect data without blocking the GUI.
class ThreadedDataFetcher(threading.Thread):
    def __init__(self, data_queue, interval=1.0):
        super().__init__()
        self.daemon = True  # This thread will exit when the main program exits
        self.data_queue = data_queue
        self.interval = interval
        self.running = True
        self.history = {
            "CPU": [], "RAM": [], "GPU": [],
            "DISK_read": [], "DISK_write": [],
            "NET_recv": [], "NET_sent": []
        }
        # State for network/disk is now correctly managed inside monitor_core.

    def run(self):
        while self.running:
            # Fetch all metrics directly from monitor_core functions
            cpu = core.get_cpu_usage(interval=None) # Non-blocking call
            ram_percent = core.get_ram_usage()
            gpu = core.get_gpu_usage()
            
            # These functions now handle the rate calculation internally
            read_mb, write_mb = core.get_disk_io()
            net_recv_mb, net_sent_mb = core.get_network_io()

            # Consolidate data for history update
            data_map = {
                "CPU": cpu, "RAM": ram_percent, "GPU": gpu,
                "DISK_read": read_mb, "DISK_write": write_mb,
                "NET_recv": net_recv_mb, "NET_sent": net_sent_mb
            }

            # Append to history, maintaining a fixed size
            for key, value in data_map.items():
                if value is not None:
                    self.history[key].append(value)
                    if len(self.history[key]) > MAX_POINTS:
                        self.history[key].pop(0)

            # Put the new data on the queue for the main thread
            self.data_queue.put(self.history.copy())
            
            time.sleep(self.interval)

    def stop(self):
        self.running = False


# This class encapsulates all drawing logic and state.
class CRTGrapher:
    def __init__(self, canvas, io_canvas, max_io, style, io_read_bar, io_write_bar, io_read_lbl, io_write_lbl):
        self.canvas = canvas
        self.io_canvas = io_canvas
        self.max_io = max_io
        self.style = style
        self.io_read_bar = io_read_bar
        self.io_write_bar = io_write_bar
        self.io_read_lbl = io_read_lbl
        self.io_write_lbl = io_write_lbl
        self.frame_count = 0

    def smooth_data(self, data, window_size=5):
        """Manual data smoothing without a library."""
        if not data: return []
        smoothed = []
        for i in range(len(data)):
            start_index = max(0, i - window_size + 1)
            window = data[start_index:i + 1]
            average = sum(window) / len(window)
            smoothed.append(average)
        return smoothed

    def draw_crt_grid(self, canvas, x_offset=0):
        w, h = canvas.winfo_width(), canvas.winfo_height()
        if w < 10 or h < 10: return
        canvas.delete("grid")
        grid_spacing = max(1, w // 10)
        for x in range(-grid_spacing, w, grid_spacing):
            canvas.create_line(x + x_offset, 0, x + x_offset, h, fill=CRT_GRID, tags="grid")
        for y in range(0, h, max(1, h // 5)):
            canvas.create_line(0, y, w, y, fill=CRT_GRID, tags="grid")

    def _get_points(self, canvas, data, max_value):
        """Generates a consistent list of points for both the line and the fill."""
        w, h = canvas.winfo_width(), canvas.winfo_height()
        if len(data) < 2 or w < 10 or h < 10: return []
        
        plot_data = ([0] * (MAX_POINTS - len(data))) + data[-MAX_POINTS:]
        step = w / max(1, MAX_POINTS -1)
        
        points = []
        for i, val in enumerate(plot_data):
            x = i * step
            y = h - (val / max(1e-6, max_value)) * h
            points.append((x, y))
        return points

    def draw_crt_line(self, canvas, data, max_value, line_color, width=2, tags="line"):
        canvas.delete(tags)
        points = self._get_points(canvas, data, max_value)
        if not points: return
        flat_pts = [coord for pt in points for coord in pt]
        canvas.create_line(*flat_pts, fill=line_color, width=width, smooth=True, splinesteps=CRT_LINE_SMOT, tags=tags)

    def draw_filled_area(self, canvas, data, max_value, fill_color, tags="fill"):
        canvas.delete(tags)
        points = self._get_points(canvas, data, max_value)
        if not points: return
        
        poly_pts = [points[0]] + points + [(points[-1][0], canvas.winfo_height()), (points[0][0], canvas.winfo_height())]
        flat_pts = [coord for pt in poly_pts for coord in pt]
        canvas.create_polygon(*flat_pts, fill=fill_color, outline="", tags=tags)

    def draw_dual_io(self, read_hist, write_hist):
        self.io_canvas.delete("all")
        w = self.io_canvas.winfo_width()
        grid_spacing = max(1, w // 10)
        x_offset = -(self.frame_count * 3) % grid_spacing
        self.draw_crt_grid(self.io_canvas, x_offset)

        max_val = max(read_hist + write_hist + [1])
        smoothed_read = self.smooth_data(read_hist)
        smoothed_write = self.smooth_data(write_hist)
        
        self.draw_filled_area(self.io_canvas, smoothed_read, max_val, "#224422", tags="read_fill")
        self.draw_filled_area(self.io_canvas, smoothed_write, max_val, "#606060", tags="write_fill")
        
        self.draw_crt_line(self.io_canvas, smoothed_read, max_val, CRT_GREEN, tags="read_line")
        self.draw_crt_line(self.io_canvas, smoothed_write, max_val, "white", tags="write_line")

    def draw_metric(self, canvas, series, max_value, color):
        canvas.delete("all")
        w = canvas.winfo_width()
        grid_spacing = max(1, w // 10)
        x_offset = -(self.frame_count * 3) % grid_spacing
        self.draw_crt_grid(canvas, x_offset)

        fill_map = {CRT_GREEN: "#224422", CRT_YELLOW: "#444422", CRT_RED: "#442222"}
        fill_color = fill_map.get(color, "#333333")

        smoothed_series = self.smooth_data(series)
        
        self.draw_filled_area(canvas, smoothed_series, max_value, fill_color)
        self.draw_crt_line(canvas, smoothed_series, max_value, color)

    def update_dual_io_labels(self, read_mb, write_mb):
        self.io_read_lbl.config(text=f"READ: {read_mb:.2f} MB/s")
        self.io_write_lbl.config(text=f"WRITE: {write_mb:.2f} MB/s")
        self.io_read_bar["value"] = min(read_mb, self.max_io)
        self.io_write_bar["value"] = min(write_mb, self.max_io)
