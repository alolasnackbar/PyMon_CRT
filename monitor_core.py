import sys
import psutil
import subprocess
import platform
import time
import shutil
import re
import os
from datetime import datetime

# ---- Optional Windows WMI (for CPU model) ----
WMI_AVAILABLE = False
if platform.system() == "Windows":
    try:
        import wmi  # type: ignore
        WMI_AVAILABLE = True
    except Exception:
        WMI_AVAILABLE = False

# ---- Helpers ----
def _which(cmd: str) -> bool:
    return shutil.which(cmd) is not None

def _run_cmd(args, timeout=0.3):
    try:
        out = subprocess.check_output(args, stderr=subprocess.DEVNULL, timeout=timeout, text=True)
        return out.strip()
    except Exception:
        return None

# ---- CPU ----
def get_cpu_usage(interval=None):
    """
    Return CPU usage percent.
    - interval=None: instantaneous (requires prior warmup call by psutil).
    - interval>0: blocks for that interval.
    """
    try:
        return psutil.cpu_percent(interval=interval)
    except Exception:
        return 0.0

# Cache values + limiter
_last_freq_check = 1.0
_last_freq = None
_freq_min = None
_freq_max = None

def get_cpu_freq(rate_limit_sec: float = 1.0):
    """
    Returns a tuple (current_GHz, min_GHz, max_GHz).
    - `current_GHz`: updated at most once per `rate_limit_sec` to reduce WMI overhead.
    - `min_GHz`, `max_GHz`: cached once at startup (since they rarely change).
    Returns None if unavailable.
    """
    global _last_freq_check, _last_freq, _freq_min, _freq_max

    try:
        now = time.time()

        # Initialize min/max once
        if _freq_min is None or _freq_max is None:
            f = psutil.cpu_freq(percpu=False)
            if f:
                _freq_min = round(f.min / 1000.0, 2) if f.min else None
                _freq_max = round(f.max / 1000.0, 2) if f.max else None

        # Rate-limit the "current" lookup
        if now - _last_freq_check >= rate_limit_sec or _last_freq is None:
            f = psutil.cpu_freq(percpu=False)
            if f:
                _last_freq = round(f.current / 1000.0, 2)  # GHz
            else:
                _last_freq = None
            _last_freq_check = now

        return (_last_freq, _freq_min, _freq_max)

    except Exception:
        return None

# ---- CPU Info (cached) ----
_cpu_model_cache = None
def get_cpu_info():
    global _cpu_model_cache
    if _cpu_model_cache is None:
        model = None
        try:
            if platform.system() == "Windows" and WMI_AVAILABLE:
                c = wmi.WMI()  # type: ignore
                model = c.Win32_Processor()[0].Name
            elif platform.system() == "Darwin":
                out = _run_cmd(["sysctl", "-n", "machdep.cpu.brand_string"])
                model = out or platform.processor()
            else:
                out = _run_cmd(["lscpu"])
                if out:
                    for line in out.splitlines():
                        if "Model name" in line:
                            model = line.split(":", 1)[1].strip()
                            break
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
                    model = platform.processor() or platform.uname().processor
        except Exception:
            model = platform.processor() or "Unknown CPU"
        _cpu_model_cache = model or "Unknown CPU"

    return {
        "model": _cpu_model_cache,
        "physical_cores": psutil.cpu_count(logical=False) or 0,
        "logical_cores": psutil.cpu_count(logical=True) or 0,
    }

# ---- CPU htop Process Table ----
def get_load_average():
    """Return load average in Linux style, Windows shows CPU percent fallback."""
    try:
        load1, load5, load15 = os.getloadavg()
        return f"Load average: {load1:.2f} {load5:.2f} {load15:.2f}"
    except (AttributeError, OSError):
        # Windows fallback: show CPU usage %
        cpu = psutil.cpu_percent(interval=1)
        return f"CPU Usage: {cpu:.1f}%"
    
def get_top_processes(limit=3):
    """Return top processes sorted by CPU usage (safe across platforms)."""
    processes = []
    for p in psutil.process_iter(['pid', 'username', 'nice', 'memory_info', 'cpu_percent', 'name']):
        try:
            info = p.info
            virt = (info.get('memory_info').vms if info.get('memory_info') else 0) / (1024 * 1024)
            res = (info.get('memory_info').rss if info.get('memory_info') else 0) / (1024 * 1024)
            processes.append((
                info.get('pid', 0),
                (info.get('username') or "unknown")[:8],
                info.get('nice', 0),  # fallback to 0 if missing
                virt,
                res,
                info.get('cpu_percent', 0.0),
                p.memory_percent() if p else 0.0,
                info.get('name', "unknown")
            ))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    # Sort by CPU%
    processes.sort(key=lambda x: x[5], reverse=True)

    top = []
    for proc in processes[:limit]:
        pid, user, nice, virt, res, cpu, mem, name = proc
        top.append(
            f"{pid:<6} {user:<8} {virt:>6.1f}M {res:>6.1f}M {cpu:>5.1f} {mem:>5.1f}  {name}"
        )
    return top

# ---- RAM ----
def get_ram_usage():
    try:
        return psutil.virtual_memory().percent
    except Exception:
        return 0.0

def get_ram_info():
    try:
        mem = psutil.virtual_memory()
        return {
            "used": round(mem.used / (1024**3), 2),
            "available": round(mem.available / (1024**3), 2),
        }
    except Exception:
        return {"used": 0.0, "available": 0.0}

# ---- Disk I/O (rate based on actual elapsed) ----
_last_disk_io = psutil.disk_io_counters()
_last_disk_ts = time.time()

def get_disk_io(interval=None):
    """
    Returns (read_MB_per_s, write_MB_per_s).
    Uses actual elapsed time since the previous call for accuracy.
    The 'interval' parameter is accepted for API compatibility but is not used to sleep.
    """
    global _last_disk_io, _last_disk_ts
    try:
        now = time.time()
        io_now = psutil.disk_io_counters()
        elapsed = max(1e-3, now - _last_disk_ts)  # avoid div by zero

        read_bytes = io_now.read_bytes - _last_disk_io.read_bytes
        write_bytes = io_now.write_bytes - _last_disk_io.write_bytes

        _last_disk_io = io_now
        _last_disk_ts = now

        read_mb_s = read_bytes / (1024 * 1024) / elapsed
        write_mb_s = write_bytes / (1024 * 1024) / elapsed
        return read_mb_s, write_mb_s
    except Exception:
        return 0.0, 0.0
# --- DISK space usage ---
def get_disk_summary(max_drives=3):
    """
    Returns a formatted string of disk usage for up to `max_drives` drives.
    
    Example output: "C: 120/500 GB | D: 300/1.1 GB"
    """
    summary = []
    try:
        partitions = psutil.disk_partitions()
        count = 0
        for part in partitions:
            if count >= max_drives:
                break
            try:
                usage = psutil.disk_usage(part.mountpoint)
                used_gb = round(usage.used / (1024 ** 3), 1)
                total_gb = round(usage.total / (1024 ** 3), 1)
                # Remove any trailing '\' or ':' from the drive letter
                drive_letter = part.device.strip(':\\')
                summary.append(f"{drive_letter}: {used_gb}/{total_gb} GB")
                count += 1
            except PermissionError:
                continue
    except Exception as e:
        print("Error retrieving disk summary:", e)
        return ""
    
    return " | ".join(summary)

# ---- GPU ----
def _nvidia_smi_available():
    return _which("nvidia-smi")

def get_gpu_usage():
    """
    Returns GPU utilization percent (float) or None if not available.
    NVIDIA only (via nvidia-smi).
    """
    if not _nvidia_smi_available():
        return None
    out = _run_cmd(["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"], timeout=0.25)
    if not out:
        return None
    try:
        return float(out.splitlines()[0].strip())
    except Exception:
        return None

def get_gpu_info():
    if not _nvidia_smi_available():
        return None
    out = _run_cmd(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], timeout=0.25)
    return out if out else None

# ---- Time & Uptime ----
def get_local_date():
    """Return the current local date as a formatted string."""
    return datetime.now().strftime("%a, %b %d, %Y")

def get_local_time():
    """Return the current local time as a formatted string."""
    return datetime.now().strftime("%H:%M:%S %p")

def get_uptime():
    try:
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}h {minutes}m {seconds}s"
    except Exception:
        return "N/A"

# --- Network selection ---
def get_primary_interface():
    """
    Auto-select the main active interface, ignoring loopback and common virtuals.
    """
    try:
        stats = psutil.net_io_counters(pernic=True)
        candidates = []
        for iface, data in stats.items():
            low = iface.lower()
            if low in ("lo", "loopback") or "docker" in low or "veth" in low or "virtual" in low:
                continue
            if data.bytes_sent > 0 or data.bytes_recv > 0:
                candidates.append(iface)
        return candidates[0] if candidates else None
    except Exception:
        return None

# --- Ping (with timeouts and robust parsing) ---
def ping_host(host="8.8.8.8", count=3, timeout=1.5):
    """
    Ping host and return average latency in ms (float) or None.
    Works on Windows/macOS/Linux.
    """
    param = "-n" if platform.system().lower() == "windows" else "-c"
    try:
        output = subprocess.check_output(
            ["ping", param, str(count), host],
            universal_newlines=True,
            stderr=subprocess.DEVNULL,
            timeout=timeout
        )
    except Exception:
        return None

    # Try Windows "Average = 12ms"
    m = re.search(r"Average\s*=\s*(\d+(?:\.\d+)?)\s*ms", output, re.IGNORECASE)
    if m:
        return float(m.group(1))

    # Try Linux/macOS "min/avg/max/mdev = a/b/c/d ms"
    m = re.search(r"=\s*([\d\.]+)/([\d\.]+)/", output)
    if m:
        try:
            return float(m.group(2))
        except Exception:
            return None

    # Fallback: last number with 'ms' on line containing avg
    for line in output.splitlines():
        if "avg" in line or "Average" in line or "round-trip" in line or "rtt" in line:
            nums = re.findall(r"[\d\.]+", line)
            if nums:
                try:
                    return float(nums[-1])
                except Exception:
                    pass
    return None

def net_usage_latency(interface=None, ping_host_addr="8.8.8.8", ping_count=3, interval=1):
    """
    Return (net_in_MB_per_s, net_out_MB_per_s, avg_latency_ms).
    Sleeps for 'interval' seconds to sample I/O deltas.
    Intended for use in a background thread.
    """
    try:
        if interface is None:
            interface = get_primary_interface()
        if interface is None:
            return 0.0, 0.0, None

        pernic1 = psutil.net_io_counters(pernic=True)
        if interface not in pernic1:
            return 0.0, 0.0, None

        bytes_recv1 = pernic1[interface].bytes_recv
        bytes_sent1 = pernic1[interface].bytes_sent

        time.sleep(interval)

        pernic2 = psutil.net_io_counters(pernic=True)
        if interface not in pernic2:
            return 0.0, 0.0, None

        bytes_recv2 = pernic2[interface].bytes_recv
        bytes_sent2 = pernic2[interface].bytes_sent

        net_in_MB = round((bytes_recv2 - bytes_recv1) / 1024 / 1024 / interval, 3)
        net_out_MB = round((bytes_sent2 - bytes_sent1) / 1024 / 1024 / interval, 3)

        avg_latency = ping_host(ping_host_addr, ping_count)
        return net_in_MB, net_out_MB, avg_latency
    except Exception:
        return 0.0, 0.0, None

# ---- Top CPU Process (expensive; keep optional) ----
def get_top_cpu_process():
    """
    Returns (name, cpu_percent) of the top CPU process.
    Note: potentially expensive; call sparingly or in a background thread.
    """
    try:
        processes = []
        for proc in psutil.process_iter(['name', 'cpu_percent']):
            try:
                cpu = proc.info['cpu_percent']
                if cpu == 0.0:
                    cpu = proc.cpu_percent(interval=0.1)
                processes.append((proc.info['name'] or "Unknown", cpu))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        if not processes:
            return ("N/A", 0.0)
        return max(processes, key=lambda x: x[1])
    except Exception:
        return ("N/A", 0.0)

# ---- GPU VRAM Usage (optional; Linux best) ----
def get_gpu_vram():
    """
    Returns (used_GB, total_GB) or (None, None).
    Requires GPUtil on Windows; more reliable on Linux.
    """
    try:
        import GPUtil  # type: ignore
        gpus = GPUtil.getGPUs()
        if not gpus:
            return None, None
        gpu = gpus[0]
        used = round(gpu.memoryUsed / 1024, 2)
        total = round(gpu.memoryTotal / 1024, 2)
        return used, total
    except Exception:
        return None, None
