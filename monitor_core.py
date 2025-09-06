import sys
import psutil
import subprocess
import platform
import wmi
from datetime import datetime, timedelta

# ---- CPU ----
def get_cpu_usage(interval=0.1):
    return psutil.cpu_percent(interval=interval)

def get_cpu_freq():
    max_freq = psutil.cpu_freq(percpu=True)
    cpu_percent = psutil.cpu_percent(interval=0.1)  # get current usage
    if max_freq is not None:
        freq_avg = sum(f.current for f in max_freq) / len(max_freq)
        estimated = freq_avg * (cpu_percent / 100) 
        #print("freqav",freq_avg,"estimate", estimated)
        return round(estimated + freq_avg, 2)  # in MHz estimated not real ghz
    return None

# ---- CPU Info (cached model) ----
_cpu_model_cache = None

def get_cpu_info():
    global _cpu_model_cache
    if _cpu_model_cache is None:
        model = None
        if platform.system() == "Windows":
            try:
                c = wmi.WMI()
                model = c.Win32_Processor()[0].Name
            except Exception:
                model = platform.processor()
        else:
            # Try to use lscpu or /proc/cpuinfo for Linux
            try:
                out = subprocess.check_output("lscpu", shell=True).decode()
                for line in out.splitlines():
                    if "Model name" in line:
                        model = line.split(":", 1)[1].strip()
                        break
            except Exception:
                pass
            if not model:
                try:
                    with open("/proc/cpuinfo") as f:
                        for line in f:
                            if "model name" in line:
                                model = line.split(":", 1)[1].strip()
                                break
                except Exception:
                    pass
            if not model:
                model = platform.processor()
        _cpu_model_cache = model

    return {
        "model": _cpu_model_cache,
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

# ---- Time & Uptime ----
def get_local_time():
    return datetime.now().strftime("%a, %b %d, %Y | %H:%M:%S")

def get_uptime():
    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.now() - boot_time
    hours, remainder = divmod(uptime.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"

def main():
    if not hasattr(psutil, "sensors_temperatures"):
        sys.exit("platform not supported")
    temps = psutil.sensors_temperatures()
    if not temps:
        sys.exit("can't read any temperature")
    for name, entries in temps.items():
        print(name)
        for entry in entries:
            line = "    {:<20} {} °C (high = {} °C, critical = %{} °C)".format(
                entry.label or name,
                entry.current,
                entry.high,
                entry.critical,
            )
            print(line)
        print()

if __name__ == '__main__':
    main()
    
# ---- Top CPU Process ----
def get_top_cpu_process(): #very DEMANDING UNUSED
    """Returns (name, cpu_percent) of the process using the most CPU."""
    processes = []
    for proc in psutil.process_iter(['name', 'cpu_percent']):
        try:
            cpu = proc.info['cpu_percent']
            if cpu == 0.0:
                cpu = proc.cpu_percent(interval=0.1)
            processes.append((proc.info['name'], cpu))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    if not processes:
        return ("N/A", 0.0)
    top = max(processes, key=lambda x: x[1])
    return top

# ---- GPU VRAM Usage ----
def get_gpu_vram(): #required library GPUtil for wins/ only working in linux
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

print("all working no bug yet...")