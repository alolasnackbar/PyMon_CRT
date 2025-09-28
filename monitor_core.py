import psutil
import subprocess
import platform
import time
import shutil
import re
import os
import sys
from datetime import datetime

# ---- Optional Windows WMI (for CPU model & temperature) ----
WMI_AVAILABLE = False
if platform.system() == "Windows":
    try:
        import wmi  # type: ignore
        WMI_AVAILABLE = True
    except Exception:
        WMI_AVAILABLE = False

# ---- Helpers ----
def _which(cmd: str) -> bool:
    """Check if a command is available in the system's PATH."""
    return shutil.which(cmd) is not None

def _run_cmd(args, timeout=0.3):
    """Run a subprocess command and return its output."""
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
            system = platform.system()
            if system == "Windows":
                # Detect actual CPU model on Windows using WMI for a cleaner name
                out = _run_cmd(["wmic", "cpu", "get", "Name", "/value"])
                if out:
                    # Parse output (e.g., "Name=Intel(R) Core(TM) i7-13700K CPU @ 3.40GHz")
                    for line in out.splitlines():
                        if line.startswith("Name="):
                            model = line.split("=", 1)[1].strip()
                            break
            elif system == "Darwin":
                out = _run_cmd(["sysctl", "-n", "machdep.cpu.brand_string"])
                model = out or platform.processor()
            else:  # Linux or other Unix
                out = _run_cmd(["lscpu"])
                if out:
                    for line in out.splitlines():
                        if "Model name" in line:
                            model = line.split(":", 1)[1].strip()
                            break
                # Fallback to /proc/cpuinfo
                if not model:
                    try:
                        with open("/proc/cpuinfo") as f:
                            for line in f:
                                if "model name" in line:
                                    model = line.split(":", 1)[1].strip()
                                    break
                    except Exception:
                        pass
                # Final fallback
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

def get_cpu_temp():
    """
    Returns CPU temperature in Celsius, or None if not available.
    Supports `psutil.sensors_temperatures()` as the primary method for all platforms,
    with a robust search for common sensor names.
    """
    try:
        temps = psutil.sensors_temperatures()
        if not temps:
            return None

        # Tier 1: Look for common, explicit CPU/Core temperature sensors
        for name, sensors in temps.items():
            if sensors and any(kw in name.lower() for kw in ['cpu', 'core', 'package']):
                # Return the first found valid current temperature
                for sensor in sensors:
                    if sensor.current is not None:
                        return sensor.current

        # Tier 2: General fallback for any sensor that seems like a temperature reading
        for name, sensors in temps.items():
            if sensors and any(kw in name.lower() for kw in ['temp', 'thermal']):
                for sensor in sensors:
                    if sensor.current is not None:
                        return sensor.current

    except Exception:
        pass
    
    # Windows-specific WMI fallback
    if platform.system() == "Windows" and WMI_AVAILABLE:
        try:
            # FIX: Use a raw string (r"...") to avoid SyntaxWarning from '\w'
            w = wmi.WMI(namespace=r"root\wmi")
            temperature_info = w.MSAcpi_ThermalZoneTemperature()
            if temperature_info:
                # Temperature is in tenths of Kelvin
                return (temperature_info[0].CurrentTemperature / 10) - 273.15
        except Exception:
            pass

    return None

# ---- CPU htop Process Table ----
def get_load_average():
    """Return load average in Linux style, Windows shows CPU percent fallback."""
    try:
        load1, load5, load15 = os.getloadavg()
        return f"{load1:.2f} {load5:.2f} {load15:.2f}"#load average view here
    except (AttributeError, OSError):
        # Windows fallback: show CPU usage %
        cpu = psutil.cpu_percent(interval=1)
        return f"{cpu:.1f}"#load cpu usage here
    
def get_top_processes(limit=5):
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
                info.get('nice', 0),  # fallback to 0 if missing nice is what?
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
    
def _rocm_smi_available():
    return _which("rocm-smi")

def get_gpu_usage():
    """
    Returns GPU utilization percent (float) or None if not available.
    Supports NVIDIA (via nvidia-smi) and AMD (via rocm-smi on Linux).
    """
    try:
        if _nvidia_smi_available():
            out = _run_cmd(["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"], timeout=0.25)
            if out:
                return float(out.splitlines()[0].strip())
        elif platform.system() == "Linux" and _rocm_smi_available():
            out = _run_cmd(["rocm-smi", "--showuse", "--json"], timeout=0.25)
            if out:
                import json
                data = json.loads(out)
                # Parse the usage data from the JSON output
                # The exact key may vary; this is a common one.
                gpus = data.get("GPUs", [])
                if gpus and gpus[0].get("GPU use (%)"):
                    # The value might be a string like "50.0%"
                    return float(gpus[0]["GPU use (%)"].strip('% '))

    except Exception:
        return None
    return None

def get_gpu_clock_speed():
    """
    Returns the live GPU clock speed from nvidia-smi as a string.
    Returns "N/A" if nvidia-smi is not available or an error occurs.
    """
    # A simplified, reliable check for nvidia-smi
    nvidia_smi_path = "nvidia-smi"
    if os.name == 'nt' and not os.path.exists(os.path.join(os.environ.get('ProgramFiles', ''), 'NVIDIA Corporation', 'NVSMI', 'nvidia-smi.exe')):
        # On Windows, check common install path if not in PATH
        # This part of the logic is a basic check.
        # A more robust check might involve more paths or try/except
        pass
    else:
        try:
            subprocess.run([nvidia_smi_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            return "N/A"

    # Use subprocess.check_output to capture the command's output
    try:
        output = subprocess.check_output([nvidia_smi_path, "--query-gpu=clocks.sm", "--format=csv,noheader,nounits"], universal_newlines=True)
        # The output is a string like "1845" (for a clock speed of 1845 MHz)
        clock_speed_mhz = float(output.strip()) 
        
        # Format the output into a more readable string
        return f"{clock_speed_mhz:>.0f}"

    except (subprocess.CalledProcessError, FileNotFoundError, IndexError, ValueError) as e:
        # Handle all potential errors
        return "N/A"


def get_gpu_temp():
    """
    Returns GPU temperature in Celsius, or None if not available.
    Supports NVIDIA (via nvidia-smi) and AMD (via rocm-smi on Linux).
    """
    try:
        if _nvidia_smi_available():
            out = _run_cmd(["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"], timeout=0.25)
            if out:
                return float(out.splitlines()[0].strip())
        elif platform.system() == "Linux" and _rocm_smi_available():
            out = _run_cmd(["rocm-smi", "--showtemp", "--json"], timeout=0.25)
            if out:
                import json
                data = json.loads(out)
                gpus = data.get("GPUs", [])
                if gpus and gpus[0].get("Temperature (Sensor)"):
                    temp_data = gpus[0]["Temperature (Sensor)"]
                    if isinstance(temp_data, dict) and "temp (C)" in temp_data:
                        # Some versions return temp as a dict
                        return float(temp_data["temp (C)"])
                    # Some versions return a direct string
                    return float(temp_data.strip(' C'))

    except Exception:
        return None
    return None

def get_gpu_info():
    if _nvidia_smi_available():
        out = _run_cmd(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], timeout=0.25)
        return out if out else "NVIDIA GPU"
    elif platform.system() == "Linux" and _rocm_smi_available():
        out = _run_cmd(["rocm-smi", "--showproductname"], timeout=0.25)
        return out.splitlines()[-1] if out else "AMD GPU"
    elif platform.system() == "Windows" and WMI_AVAILABLE:
        try:
            w = wmi.WMI()
            gpus = w.Win32_VideoController()
            if gpus:
                # Prioritize NVIDIA and AMD names
                for gpu in gpus:
                    if "NVIDIA" in gpu.name:
                        return gpu.name
                    if "AMD" in gpu.name:
                        return gpu.name
                # Fallback to the first found GPU
                return gpus[0].name
        except Exception:
            pass
    return None


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
    Returns "WiFi", "Ethernet", or None.
    """
    try:
        stats = psutil.net_io_counters(pernic=True)
        # Prioritize interfaces based on naming conventions
        for iface, data in stats.items():
            low = iface.lower()
            if low in ("lo", "loopback") or "docker" in low or "veth" in low or "virtual" in low:
                continue
            if data.bytes_sent > 0 or data.bytes_recv > 0:
                if "eth" in low or "lan" in low:
                    return "Ethernet"
                elif "wlan" in low or "wifi" in low:
                    return "WiFi"
        
        # Fallback to the first active candidate if no naming convention match
        candidates = []
        for iface, data in stats.items():
            low = iface.lower()
            if low in ("lo", "loopback") or "docker" in low or "veth" in low or "virtual" in low:
                continue
            if data.bytes_sent > 0 or data.bytes_recv > 0:
                candidates.append(iface)
        
        if candidates:
            # Check the first candidate by its name
            first_iface_low = candidates[0].lower()
            if "eth" in first_iface_low or "lan" in first_iface_low:
                return "Ethernet"
            elif "wlan" in first_iface_low or "wifi" in first_iface_low:
                return "WiFi"
            else:
                # Can't determine type from name
                return None
        return None
    except Exception:
        return None

# --- Ping (with timeouts and robust parsing) ---
def ping_host(host_address, ping_count=3):
    """
    Pings a host and returns the average latency in milliseconds.
    
    Args:
        host_address (str): The IP address or hostname to ping.
        ping_count (int): The number of pings to send.
        
    Returns:
        float: The average latency in milliseconds, or None if ping fails.
    """
    try:
        # Use a cross-platform command
        command = ['ping', host_address, '-n' if os.name == 'nt' else '-c', str(ping_count)]
        
        # Run the command and capture the output
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10,
            check=True
        )

        # Parse the output to find the average latency
        output = result.stdout
        if os.name == 'nt':  # Windows
            # Look for "Average = 12ms"
            match = re.search(r'Average = (\d+)ms', output)
        else:  # Linux/macOS
            # Look for "min/avg/max/mdev = 10.123/12.345/14.567/1.234"
            match = re.search(r'min/avg/max/.+ = [\d.]+/([\d.]+)', output)

        if match:
            # Return the average latency as a float
            return float(match.group(1))
        
        return None  # No match found
        
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        print(f"Ping failed: {e}")
        return None

def net_usage_latency(interface="Ethernet", ping_host_addr="8.8.8.8", ping_count=3, interval=0.1):
    """
    Return (net_in_MB_per_s, net_out_MB_per_s, avg_latency_ms).
    Samples I/O deltas and measures latency.
    """
    # Initialize values to default
    net_in_MB, net_out_MB, avg_latency = 0.0, 0.0, None
    
    try:
        if interface is None:
            interface = get_primary_interface()
        if interface is None:
            return 0.0, 0.0, None

        # 1. Get Network Usage
        try:
            pernic1 = psutil.net_io_counters(pernic=True)
            if interface not in pernic1:
                return 0.0, 0.0, None

            bytes_recv1 = pernic1[interface].bytes_recv
            bytes_sent1 = pernic1[interface].bytes_sent

            time.sleep(interval)

            pernic2 = psutil.net_io_counters(pernic=True)
            if interface not in pernic2:
                # If interface disappears, return what we have
                return 0.0, 0.0, None

            bytes_recv2 = pernic2[interface].bytes_recv
            bytes_sent2 = pernic2[interface].bytes_sent

            net_in_MB = round((bytes_recv2 - bytes_recv1) / 1024 / 1024 / interval, 3)
            net_out_MB = round((bytes_sent2 - bytes_sent1) / 1024 / 1024 / interval, 3)

        except Exception as e:
            print(f"Network usage measurement failed: {e}")
            # If network usage fails, we'll return 0.0 for those values but still try to get latency
            pass

        # 2. Get Latency
        try:
            # ping_host must be a valid, accessible function
            avg_latency = ping_host(ping_host_addr, ping_count)
            # Print a success message for debugging
            # if avg_latency is not None:
            #     print(f"Ping successful, average latency: {avg_latency} ms")
            # else:
            #     print("Ping returned None.")

        except Exception as e:
            print(f"Latency measurement failed: {e}")
            # avg_latency remains None as initialized
            pass

        return net_in_MB, net_out_MB, avg_latency
        
    except Exception as e:
        # A final, broad exception for any other unexpected errors
        print(f"An unexpected error occurred: {e}")
        return 0.0, 0.0, None