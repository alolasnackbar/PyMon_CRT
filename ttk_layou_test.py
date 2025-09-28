import psutil
import subprocess
import platform
import time
import shutil
import re
import os
import sys
from datetime import datetime
import json # Added for use in GPU functions

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
        # Pass a very short interval to ensure it's not blocking the main loop
        cpu = psutil.cpu_percent(interval=0.01) 
        return f"{cpu:.1f}"#load cpu usage here
    
def get_top_processes(limit=8): # Increased limit slightly for better view
    """Return top processes sorted by CPU usage (safe across platforms)."""
    processes = []
    # psutil.process_iter() requires a warmup call to cpu_percent before the loop for accurate readings
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
            f"{pid:<6} {user:<8} {virt:>6.1f}M {res:>6.1f}M {cpu:>5.1f} {mem:>5.1f}  {name}"
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
                
                # Use just the mountpoint if it's a Unix-style path or a complex Windows path
                display_name = drive_letter if drive_letter else part.mountpoint
                
                summary.append(f"{display_name}: {used_gb}/{total_gb} GB")
                count += 1
            except PermissionError:
                continue
    except Exception as e:
        # print("Error retrieving disk summary:", e) # Keep quiet in dashboard context
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
                # import json # Already imported at top
                data = json.loads(out)
                # Parse the usage data from the JSON output
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
    if not _nvidia_smi_available():
        return "N/A" # Skip complicated path checks, rely on _which

    # Use subprocess.check_output to capture the command's output
    try:
        output = subprocess.check_output([nvidia_smi_path, "--query-gpu=clocks.sm", "--format=csv,noheader,nounits"], universal_newlines=True, stderr=subprocess.DEVNULL)
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
                # import json # Already imported at top
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
                if "eth" in low or "lan" in low or "ethernet" in low:
                    return iface # Return the actual interface name
                elif "wlan" in low or "wifi" in low:
                    return iface # Return the actual interface name
        
        # Fallback to the first active candidate if no naming convention match
        candidates = []
        for iface, data in stats.items():
            low = iface.lower()
            if low in ("lo", "loopback") or "docker" in low or "veth" in low or "virtual" in low:
                continue
            if data.bytes_sent > 0 or data.bytes_recv > 0:
                candidates.append(iface)
        
        if candidates:
            return candidates[0] # Return the actual interface name
            
        return None
    except Exception:
        return None

# --- Ping (with timeouts and robust parsing) ---
def ping_host(host_address, ping_count=3):
    """
    Pings a host and returns the average latency in milliseconds.
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
            check=False # Do not raise for non-zero exit code (e.g., partial packet loss)
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
        
        return None  # No match found or 100% loss
        
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        # print(f"Ping failed: {e}") # Suppress non-critical errors for dashboard
        return None

def net_usage_latency(interface, ping_host_addr="8.8.8.8", ping_count=1, interval=0.1):
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

        net_in_MB = round((bytes_recv2 - bytes_recv1) / 1024 / 1024 / interval, 2)
        net_out_MB = round((bytes_sent2 - bytes_sent1) / 1024 / 1024 / interval, 2)

        # 2. Get Latency (using a single ping for speed)
        avg_latency = ping_host(ping_host_addr, ping_count)
        
        return net_in_MB, net_out_MB, avg_latency
        
    except Exception as e:
        # print(f"An unexpected error occurred in net_usage_latency: {e}")
        return 0.0, 0.0, None

# ---- Main Dashboard Logic ----
def display_monitor(refresh_rate_sec=1.0):
    """
    Gathers all system metrics and prints a formatted dashboard to the console.
    """
    # Clear screen for live update
    os.system('cls' if os.name == 'nt' else 'clear')
    
    # --- System Metrics Collection ---
    
    # Static info
    cpu_info = get_cpu_info()
    gpu_model = get_gpu_info()
    
    # Dynamic/Rate-limited info
    cpu_usage = get_cpu_usage(interval=None) # Instantaneous since we slept for network
    cpu_freq = get_cpu_freq(rate_limit_sec=1.0)
    cpu_temp = get_cpu_temp()
    ram_usage = get_ram_usage()
    ram_info = get_ram_info()
    
    # Disk I/O (needs delta calculation)
    disk_read, disk_write = get_disk_io()
    disk_summary = get_disk_summary(max_drives=2)
    
    # Network I/O and Latency (includes its own sleep, so we'll adjust the main loop sleep)
    primary_iface = get_primary_interface()
    # We use a shorter interval here because this is inside the main loop
    # The actual refresh rate is controlled by the main loop sleep, this interval is just for the I/O delta
    net_in, net_out, latency = net_usage_latency(
        interface=primary_iface, 
        ping_count=1, 
        interval=0.1 # This sleep time is included in the total refresh rate
    ) 

    # --- Formatting ---

    # CPU Strings
    cpu_model_str = f"{cpu_info['model']} ({cpu_info['physical_cores']}/{cpu_info['logical_cores']} Cores)"
    cpu_freq_str = f"Curr: {cpu_freq[0]:.2f} GHz | Min: {cpu_freq[1]:.2f} GHz | Max: {cpu_freq[2]:.2f} GHz" if cpu_freq and all(cpu_freq) else "Frequency Data N/A"
    cpu_temp_str = f"{cpu_temp:.1f}°C" if cpu_temp is not None else "N/A"

    # GPU Strings
    gpu_output = []
    if gpu_model:
        gpu_usage = get_gpu_usage()
        gpu_temp = get_gpu_temp()
        gpu_clock = get_gpu_clock_speed()
        
        gpu_usage_str = f"{gpu_usage:.1f}%" if gpu_usage is not None else "N/A"
        gpu_temp_str = f"{gpu_temp:.1f}°C" if gpu_temp is not None else "N/A"
        
        gpu_output.append("-" * 70)
        gpu_output.append(f"GPU: {gpu_model}")
        gpu_output.append(f"Usage: {gpu_usage_str} | Temp: {gpu_temp_str} | Clock: {gpu_clock} MHz")
    
    # Network Strings
    interface_name = primary_iface if primary_iface else "N/A"
    latency_str = f"{latency:.2f} ms" if latency is not None else "N/A"

    # --- Display Output ---
    
    print("-" * 70)
    print(" " * 20 + " SYSTEM MONITOR DASHBOARD " + " " * 20)
    print("-" * 70)
    print(f"Date: {get_local_date():<20} Time: {get_local_time():<15} Uptime: {get_uptime()}")
    print("-" * 70)

    # CPU
    print(f"CPU: {cpu_model_str}")
    print(f"Usage: {cpu_usage:.1f}% | Temp: {cpu_temp_str}")
    print(f"Freq: {cpu_freq_str}")
    print("-" * 70)

    # RAM
    print(f"RAM: {ram_usage:.1f}% Used | {ram_info['used']:.2f} GB Used | {ram_info['available']:.2f} GB Available")
    print("-" * 70)

    # GPU
    for line in gpu_output:
        print(line)
        
    # Disk
    print(f"Disk I/O: Read: {disk_read:.2f} MB/s | Write: {disk_write:.2f} MB/s")
    print(f"Disk Space: {disk_summary}")
    print("-" * 70)

    # Network
    print(f"Network ({interface_name}): In: {net_in:.2f} MB/s | Out: {net_out:.2f} MB/s | Latency (8.8.8.8): {latency_str}")
    print("-" * 70)

    # Top Processes
    load_avg = get_load_average()
    print(f"Load Average/CPU %: {load_avg}")
    print(f"{'PID':<6} {'USER':<8} {'VIRT(M)':>6} {'RES(M)':>6} {'CPU%':>5} {'MEM%':>5} NAME")
    for process_line in get_top_processes(limit=8):
        print(process_line)
    print("-" * 70)
    
    # Calculate how much more time to sleep to hit the target refresh rate
    # net_usage_latency already slept for 0.1s
    time_to_sleep = max(0.0, refresh_rate_sec - 0.1)
    time.sleep(time_to_sleep)


def main():
    """Main execution loop for the system monitor."""
    # Warmup call for psutil.cpu_percent (needed for instantaneous reading in the loop)
    psutil.cpu_percent(interval=None) 
    
    # Initial pause to allow delta calculations to stabilize
    print("Initializing system monitor... please wait.")
    time.sleep(0.5) 
    
    # Run the main display loop
    while True:
        try:
            display_monitor(refresh_rate_sec=1.0)
        except KeyboardInterrupt:
            # os.system('cls' if os.name == 'nt' else 'clear') # Optional: clear before exit
            print("\nMonitoring stopped by user (Ctrl+C).")
            break
        except Exception as e:
            # Catches unexpected runtime errors and prevents crash (e.g., temporary command failure)
            print(f"\n[Error] An unexpected error occurred: {e}. Retrying in 1 second...")
            time.sleep(1)


if __name__ == "__main__":
    main()
