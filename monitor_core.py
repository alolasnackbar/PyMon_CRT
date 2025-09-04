import psutil
import subprocess
import platform
from datetime import datetime, timedelta

# ---- CPU ----
def get_cpu_usage(interval=0.1):
    return psutil.cpu_percent(interval=interval)

def get_cpu_info():
    return {
        "model": platform.processor(),
        "physical_cores": psutil.cpu_count(logical=False),
        "logical_cores": psutil.cpu_count(logical=True)
    }

# ---- RAM ----
def get_ram_usage():
    return psutil.virtual_memory().percent

def get_ram_info():
    mem = psutil.virtual_memory()
    return {
        "used": round(mem.used / (1024**3), 2),
        "available": round(mem.available / (1024**3), 2)
    }

# ---- Disk I/O ----
_last_disk_io = psutil.disk_io_counters()
def get_disk_io(interval=1.0):
    global _last_disk_io
    io_now = psutil.disk_io_counters()
    read_bytes = io_now.read_bytes - _last_disk_io.read_bytes
    write_bytes = io_now.write_bytes - _last_disk_io.write_bytes
    _last_disk_io = io_now
    return read_bytes / (1024*1024*interval), write_bytes / (1024*1024*interval)

# ---- GPU ----
def get_gpu_usage():
    try:
        out = subprocess.check_output(
            "nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits",
            shell=True, stderr=subprocess.DEVNULL
        ).decode().strip()
        return float(out)
    except Exception:
        return None

def get_gpu_info():
    try:
        out = subprocess.check_output(
            "nvidia-smi --query-gpu=name --format=csv,noheader",
            shell=True, stderr=subprocess.DEVNULL
        ).decode().strip()
        return out
    except Exception:
        return None
    
# ---- GPU VRAM Usage ----
def get_gpu_vram():
    """
    Returns used and total VRAM in GB.
    """
    try:
        import GPUtil
        gpu = GPUtil.getGPUs()[0]  # Take the first GPU
        used = round(gpu.memoryUsed / 1024, 2)  # Convert MB to GB
        total = round(gpu.memoryTotal / 1024, 2)
        return used, total
    except Exception:
        return None, None

# ---- Time & Uptime ----
def get_local_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def get_uptime():
    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.now() - boot_time
    hours, remainder = divmod(uptime.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
