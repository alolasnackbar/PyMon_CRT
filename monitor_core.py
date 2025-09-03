import psutil
import subprocess

# ---- CPU Usage ----
def get_cpu_usage(interval=0.1):
    """Return total CPU usage percentage."""
    return psutil.cpu_percent(interval=interval)

# ---- RAM Usage ----
def get_ram_usage():
    """Return RAM usage percentage."""
    return psutil.virtual_memory().percent

# ---- Disk Usage (space) ----
def get_disk_usage():
    """Return disk usage percentage of the root filesystem/drive."""
    try:
        return psutil.disk_usage("/").percent
    except Exception:
        return None

# ---- Disk I/O (activity) ----
_last_disk_io = psutil.disk_io_counters()

def get_disk_io(interval=1.0):
    """Return read/write MB/s over a given interval."""
    global _last_disk_io
    try:
        io_now = psutil.disk_io_counters()
        read_bytes = io_now.read_bytes - _last_disk_io.read_bytes
        write_bytes = io_now.write_bytes - _last_disk_io.write_bytes
        _last_disk_io = io_now
        return (read_bytes / (1024*1024*interval), write_bytes / (1024*1024*interval))
    except Exception:
        return (None, None)

# ---- GPU Usage ----
def get_gpu_usage():
    """Try nvidia-smi for NVIDIA GPUs, else return None."""
    try:
        out = subprocess.check_output(
            "nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits",
            shell=True, stderr=subprocess.DEVNULL
        ).decode().strip()
        return float(out)
    except Exception:
        return None
    
def get_gpu_temp():
    try:
        # Example for NVIDIA GPU on Windows/Linux using nvidia-smi
        import subprocess, platform

        if platform.system() == "Windows":
            # optional: WMI can be used here for supported GPUs
            return None
        elif platform.system() == "Linux":
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
            )
            temp = float(result.stdout.strip().split("\n")[0])
            return temp
    except Exception:
        return None

# ---- Temperature ----
def get_temp():
    """Try to get CPU temperature using psutil (if available)."""
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            # Pick the first available sensor
            for entries in temps.values():
                if entries:
                    return f"{entries[0].current:.1f}°C"
    except Exception:
        pass
    return None
