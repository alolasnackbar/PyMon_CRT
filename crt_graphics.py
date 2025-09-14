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

# Placeholder for monitor_core functions, assuming they exist
# In a real app, you would import these from your monitor_core.py file
try:
    import monitor_core as core
    import psutil
except ImportError:
    class MockMonitorCore:
        def get_cpu_usage(self): return 50.0
        def get_ram_usage(self): return 35.0
        def get_gpu_usage(self): return 20.0
        def get_disk_io(self, interval=1): return 150.0, 75.0
        def get_primary_interface(self): return "eth0"
    core = MockMonitorCore()
    class MockPsutil:
        def net_io_counters(self, pernic=True):
            if pernic:
                return {"eth0": type('MockNet', (object,), {'bytes_sent': 1000, 'bytes_recv': 2000})()}
            return type('MockNet', (object,), {'bytes_sent': 1000, 'bytes_recv': 2000})()
    psutil = MockPsutil()


# This class runs in a separate thread to collect data without blocking the GUI.
class ThreadedDataFetcher(threading.Thread):
    def __init__(self, data_queue, interval=1.0):
        super().__init__()
        self.data_queue = data_queue
        self.interval = interval
        self.running = True
        self.history = {"CPU": [], "RAM": [], "GPU": [], "DISK_read": [], "DISK_write": [], "NET_recv": [], "NET_sent": []}
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
