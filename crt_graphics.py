import ttkbootstrap as tb
from ttkbootstrap.constants import *
import threading
import queue
import time
import os
import platform
import re
import subprocess
from constants import CRT_GREEN, CRT_GRID, MAX_POINTS, CRT_LINE_SMOT, FONT_TITLE, GRAPH_HEIGHT
import monitor_core as core
import psutil

# --- Color Helper Function for Redrawing ---
def get_usage_color(value):
    """
    Determines the color for a usage value (e.g., CPU, GPU, RAM)
    based on predefined thresholds.
    """
    if value is None: return "#00FF00"  # Green
    if value < 60: return "#00FF00"      # Green
    elif value < 80: return "#FFFF00"    # Yellow
    else: return "#FF0000"               # Red

def get_temp_color_crt(value):
    """
    Determines the color for temperature values for CRT display.
    """
    if value is None: return CRT_GREEN
    if value < 50: return CRT_GREEN      # Green - cool
    elif value < 70: return "#FFFF00"    # Yellow - warm
    elif value < 85: return "#FF8800"    # Orange - hot
    else: return "#FF0000"               # Red - critical

# This class runs in a separate thread to collect data without blocking the GUI.
class ThreadedDataFetcher(threading.Thread):
    def __init__(self, data_queue, interval=1.0):
        super().__init__()
        self.data_queue = data_queue
        self.interval = interval
        self.running = True
        self.history = {
            "CPU": [], "RAM": [], "GPU": [], 
            "DISK_read": [], "DISK_write": [], 
            "NET_recv": [], "NET_sent": [],
            "CPU_temp": [], "GPU_temp": []  # Add temperature history
        }
        self.last_disk_check_time = time.time()
        self.last_net_io = psutil.net_io_counters(pernic=True) if 'psutil' in globals() else None
        self.daemon = True # This thread will exit when the main program exits
        self.primary_interface = core.get_primary_interface() if 'core' in globals() else None

    def run(self):
        while self.running:
            # CPU / RAM / GPU data
            cpu = core.get_cpu_usage()
            ram_percent = core.get_ram_usage()
            gpu = core.get_gpu_usage()

            # Temperature data
            cpu_temp = core.get_cpu_temp() if hasattr(core, 'get_cpu_temp') else None
            gpu_temp = core.get_gpu_temp() if hasattr(core, 'get_gpu_temp') else None

            # Disk I/O, calculated over a period to get MB/s
            now = time.time()
            read_mb, write_mb = core.get_disk_io(interval=self.interval)
            
            # Network I/O
            net_recv_mb, net_sent_mb = 0, 0
            current_net_io = psutil.net_io_counters(pernic=True) if 'psutil' in globals() else None
            
            if current_net_io and self.last_net_io and self.primary_interface:
                if self.primary_interface in current_net_io and self.primary_interface in self.last_net_io:
                    recv_bytes_delta = current_net_io[self.primary_interface].bytes_recv - self.last_net_io[self.primary_interface].bytes_recv
                    sent_bytes_delta = current_net_io[self.primary_interface].bytes_sent - self.last_net_io[self.primary_interface].bytes_sent
                    net_recv_mb = (recv_bytes_delta / 1024 / 1024) / self.interval
                    net_sent_mb = (sent_bytes_delta / 1024 / 1024) / self.interval
                self.last_net_io = current_net_io

            # Append to history, maintaining fixed size
            if cpu is not None: self.history["CPU"].append(cpu)
            if ram_percent is not None: self.history["RAM"].append(ram_percent)
            if gpu is not None: self.history["GPU"].append(gpu)
            if read_mb is not None: self.history["DISK_read"].append(read_mb)
            if write_mb is not None: self.history["DISK_write"].append(write_mb)
            if net_recv_mb is not None: self.history["NET_recv"].append(net_recv_mb)
            if net_sent_mb is not None: self.history["NET_sent"].append(net_sent_mb)
            if cpu_temp is not None: self.history["CPU_temp"].append(cpu_temp)
            if gpu_temp is not None: self.history["GPU_temp"].append(gpu_temp)

            for key in self.history:
                if len(self.history[key]) > MAX_POINTS:
                    self.history[key].pop(0)

            # Put the new data on the queue for the main thread to pick up
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
        self.drawing_lock = threading.Lock()
        
        # Temperature display components (will be set later)
        self.temp_canvas = None
        self.temp_cpu_lbl = None
        self.temp_gpu_lbl = None

    def set_temp_components(self, temp_canvas, temp_cpu_lbl, temp_gpu_lbl):
        """Set the temperature display components."""
        self.temp_canvas = temp_canvas
        self.temp_cpu_lbl = temp_cpu_lbl
        self.temp_gpu_lbl = temp_gpu_lbl

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
        canvas.delete("grid") # Clear old grid lines efficiently
        grid_spacing = max(1, w // 10)
        for x in range(-grid_spacing, w, grid_spacing):
            canvas.create_line(x + x_offset, 0, x + x_offset, h, fill=CRT_GRID, tags="grid")
        for y in range(0, h, max(1, h // 5)):
            canvas.create_line(0, y, w, y, fill=CRT_GRID, tags="grid")

    def _get_points(self, canvas, data, max_value):
        """Generates a consistent list of points for both the line and the fill."""
        w, h = canvas.winfo_width(), canvas.winfo_height()
        if len(data) < 2 or w < 10 or h < 10: return []
        
        # Ensure a fixed number of points for consistent width
        plot_data = ([0] * (MAX_POINTS - len(data))) + data[-MAX_POINTS:]
        step = w / MAX_POINTS
        
        # Normalize and scale data to canvas coordinates
        points = []
        for i, val in enumerate(plot_data):
            x = i * step
            y = h - (val / max(1e-6, max_value)) * h
            points.append((x, y))
        return points

    def draw_crt_line(self, canvas, data, max_value, line_color, width=2, tags="line"):
        canvas.delete(tags) # Clear old line
        points = self._get_points(canvas, data, max_value)
        if not points: return
        flat_pts = [coord for pt in points for coord in pt]
        canvas.create_line(*flat_pts, fill=line_color, width=width, smooth=True, splinesteps=CRT_LINE_SMOT, tags=tags)

    def draw_filled_area(self, canvas, data, max_value, fill_color, tags="fill"):
        canvas.delete(tags) # Clear old fill
        points = self._get_points(canvas, data, max_value)
        if not points: return
        
        # Construct the polygon points by adding the bottom corners
        poly_pts = [points[0]] + points + [(points[-1][0], canvas.winfo_height()), (points[0][0], canvas.winfo_height())]
        flat_pts = [coord for pt in poly_pts for coord in pt]
        # Removed `smooth=True` to prevent the polygon from overdrawing the line.
        canvas.create_polygon(*flat_pts, fill=fill_color, outline="", tags=tags)

    def draw_dual_io(self, read_hist, write_hist):
        self.io_canvas.delete("all")
        w = self.io_canvas.winfo_width()
        grid_spacing = max(1, w // 10)
        x_offset = -(self.frame_count * 3) % grid_spacing
        self.draw_crt_grid(self.io_canvas, x_offset)

        max_io = max(read_hist + write_hist + [1])
        smoothed_read = self.smooth_data(read_hist)
        smoothed_write = self.smooth_data(write_hist)
        
        # Draw fills first
        read_fill = "#224422"
        write_fill = "#808080"
        self.draw_filled_area(self.io_canvas, smoothed_read, max_io, read_fill, tags="read_fill")
        self.draw_filled_area(self.io_canvas, smoothed_write, max_io, write_fill, tags="write_fill")
        
        # Draw lines on top
        self.draw_crt_line(self.io_canvas, smoothed_read, max_io, CRT_GREEN, tags="read_line")
        self.draw_crt_line(self.io_canvas, smoothed_write, max_io, "white", tags="write_line")

    def draw_dual_temp(self, cpu_temp_hist, gpu_temp_hist):
        """Draw dual temperature display similar to disk I/O."""
        if not self.temp_canvas:
            return
            
        self.temp_canvas.delete("all")
        w = self.temp_canvas.winfo_width()
        grid_spacing = max(1, w // 10)
        x_offset = -(self.frame_count * 3) % grid_spacing
        self.draw_crt_grid(self.temp_canvas, x_offset)

        # Use reasonable max temp for scaling (100°C)
        max_temp = max(cpu_temp_hist + gpu_temp_hist + [100])
        smoothed_cpu = self.smooth_data(cpu_temp_hist)
        smoothed_gpu = self.smooth_data(gpu_temp_hist)
        
        # Choose colors based on current temperatures
        cpu_color = get_temp_color_crt(cpu_temp_hist[-1] if cpu_temp_hist else None)
        gpu_color = get_temp_color_crt(gpu_temp_hist[-1] if gpu_temp_hist else None)
        
        # Draw fills first
        cpu_fill = "#442222" if cpu_color == "#FF0000" else "#442200" if cpu_color == "#FF8800" else "#444400" if cpu_color == "#FFFF00" else "#224422"
        gpu_fill = "#888888" if gpu_color == "#FF0000" else "#888888" if gpu_color == "#FF8800" else "#888888" if gpu_color == "#FFFF00" else "#888888"
        
        self.draw_filled_area(self.temp_canvas, smoothed_cpu, max_temp, cpu_fill, tags="cpu_fill")
        self.draw_filled_area(self.temp_canvas, smoothed_gpu, max_temp, gpu_fill, tags="gpu_fill")
        
        # Draw lines on top
        self.draw_crt_line(self.temp_canvas, smoothed_cpu, max_temp, cpu_color, tags="cpu_line")
        self.draw_crt_line(self.temp_canvas, smoothed_gpu, max_temp, "#FFFFFF", tags="gpu_line")#white fpr GPU

    def draw_metric(self, canvas, series, max_value, color):
        canvas.delete("all")
        w = canvas.winfo_width()
        grid_spacing = max(1, w // 10)
        x_offset = -(self.frame_count * 3) % grid_spacing
        self.draw_crt_grid(canvas, x_offset)

        if color == CRT_GREEN:
            fill_color = "#224422"
        elif color == "white":
            fill_color = "#888888"
        else:
            fill_color = "#444444"

        smoothed_series = self.smooth_data(series)
        
        # Draw the filled area first, then the line, so the line is always on top.
        self.draw_filled_area(canvas, smoothed_series, max_value, fill_color)
        self.draw_crt_line(canvas, smoothed_series, max_value, color)

    def update_dual_io_labels(self, read_mb, write_mb):
        self.io_read_lbl.config(text=f"READ: {read_mb:.2f} MB/s")
        self.io_write_lbl.config(text=f"WRITE: {write_mb:.2f} MB/s")
        self.io_read_bar["value"] = min(read_mb, self.max_io)
        self.io_write_bar["value"] = min(write_mb, self.max_io)

    def update_dual_temp_labels(self, cpu_temp, gpu_temp):
        """Update temperature labels with current values and colors."""
        if self.temp_cpu_lbl and cpu_temp is not None:
            cpu_color = get_temp_color_crt(cpu_temp)
            self.temp_cpu_lbl.config(
                text=f"CPU: {cpu_temp:.1f}°C", 
                foreground=cpu_color
            )
        
        if self.temp_gpu_lbl and gpu_temp is not None:
            gpu_color = get_temp_color_crt(gpu_temp)
            self.temp_gpu_lbl.config(
                text=f"GPU: {gpu_temp:.1f}°C", 
                foreground="#FFFFFF"  # Keep GPU label cyan for consistency
            )

    def redraw_all(self, history):
        """Redraws all canvases with the latest data history."""
        # Redraw CPU/GPU/RAM graphs
        if "CPU" in history and self.canvas:
            cpu_val = history["CPU"][-1] if history["CPU"] else 0
            self.draw_metric(self.canvas, history["CPU"], 100, color=get_usage_color(cpu_val))
        
        # Re-draw the IO canvas
        if "DISK_read" in history and "DISK_write" in history and self.io_canvas:
            self.draw_dual_io(history["DISK_read"], history["DISK_write"])
            
        # Re-draw the temperature canvas
        if "CPU_temp" in history and "GPU_temp" in history and self.temp_canvas:
            self.draw_dual_temp(history["CPU_temp"], history["GPU_temp"])