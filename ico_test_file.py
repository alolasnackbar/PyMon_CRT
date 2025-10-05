# import tkinter as tk, os, sys
# def resource_path(rel_path):
#     if getattr(sys, "frozen", False):
#         base = os.path.dirname(sys.executable)
#     else:
#         base = os.path.dirname(os.path.abspath(__file__))
#     return os.path.join(base, rel_path)

# root = tk.Tk()
# try:
#     root.iconbitmap(resource_path("nohead_test.ico"))
#     print("ICON: loaded OK")
# except Exception as e:
#     print("ICON LOAD ERROR:", type(e).__name__, e)
# root.destroy()

import psutil
import platform
import subprocess
import time
# ---- Optional Windows WMI (for CPU model & temperature) ----
WMI_AVAILABLE = False
if platform.system() == "Windows":
    try:
        import wmi  # type: ignore
        WMI_AVAILABLE = True
    except Exception:
        WMI_AVAILABLE = False

import wmi

# Global cache variables
_last_freq_check = 0
_last_freq = None
_freq_min = None
_freq_max = None
_freq_base = None  # Base frequency for calculations

# Try to import win32pdh, but don't fail if not available
try:
    import win32pdh
    import win32api
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

def get_cpu_temperature():
    """
    Retrieves the CPU temperature in Celsius using WMI.
    Returns:
        float: The CPU temperature in Celsius, or None if not found.
    """
    try:
        c = wmi.WMI(namespace="root\\wmi")
        temperature_info = c.MSAcpi_ThermalZoneTemperature()

        if temperature_info:
            # The temperature is returned in tenths of a Kelvin.
            # Convert to Celsius: (Kelvin / 10) - 273.15
            temp_kelvin_tenths = temperature_info[0].CurrentTemperature
            temp_celsius = (temp_kelvin_tenths / 10.0) - 273.15
            return temp_celsius
        else:
            print("Could not find CPU temperature information via WMI.")
            return None
    except wmi.x_wmi as e:
        print(f"WMI error: {e}")
        print("Ensure you have administrative privileges if encountering access denied errors.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None

import time
import subprocess
import platform
import psutil

# Global cache variables
_last_freq_check = 0
_last_freq = None
_freq_min = None
_freq_max = None
_freq_base = None

import time
import psutil

# Global cache variables
_last_freq_check = 0
_last_freq = None
_freq_min = None
_freq_max = None
_freq_base = None

# Try to import win32pdh, but don't fail if not available
try:
    import win32pdh
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False


def get_cpu_freq(rate_limit_sec: float = 1.0):
    """
    Returns a tuple (current_GHz, min_GHz, max_GHz).
    - `current_GHz`: live frequency updated at most once per `rate_limit_sec`.
    - `min_GHz`, `max_GHz`: cached once at startup.
    Returns (None, None, None) if unavailable.
    
    Uses Windows Performance Counters for real-time frequency data including turbo boost.
    Requires pywin32: pip install pywin32
    """
    global _last_freq_check, _last_freq, _freq_min, _freq_max, _freq_base
    
    try:
        now = time.time()
        
        # Initialize min/max/base once
        if _freq_min is None or _freq_max is None or _freq_base is None:
            try:
                f = psutil.cpu_freq(percpu=False)
                if f:
                    _freq_min = round(f.min / 1000.0, 2) if f.min and f.min > 0 else None
                    _freq_max = round(f.max / 1000.0, 2) if f.max and f.max > 0 else None
                    _freq_base = f.max if f.max and f.max > 0 else None
            except Exception:
                pass
            
            # If we don't have base from psutil, MUST get it from WMI
            if _freq_base is None:
                _freq_base = _get_base_frequency_wmi()
            
            # Last resort: if we still don't have base, try to get from current
            if _freq_base is None:
                try:
                    f = psutil.cpu_freq(percpu=False)
                    if f and f.current and f.current > 0:
                        _freq_base = f.current
                except Exception:
                    pass
        
        # Rate-limit the "current" lookup
        if now - _last_freq_check >= rate_limit_sec or _last_freq is None:
            current_freq = _get_live_cpu_freq_windows()
            _last_freq = round(current_freq / 1000.0, 2) if current_freq else None
            _last_freq_check = now
        
        return (_last_freq, _freq_min, _freq_max)
    
    except Exception:
        return (None, None, None)


def _get_base_frequency_wmi():
    """Get the base/nominal CPU frequency from WMI (one-time lookup)"""
    try:
        import subprocess
        result = subprocess.run(
            ['wmic', 'cpu', 'get', 'MaxClockSpeed'],
            capture_output=True,
            text=True,
            timeout=2,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            for line in lines[1:]:
                line = line.strip()
                if line and line.isdigit():
                    return float(line)  # Returns MHz
    except Exception:
        pass
    return None


def _get_live_cpu_freq_windows():
    """
    Get live CPU frequency on Windows using Performance Counters.
    Returns frequency in MHz or None if unavailable.
    """
    if not WIN32_AVAILABLE:
        return _get_freq_psutil()
    
    # Try Performance Counter method (most accurate for live data)
    freq = _get_freq_performance_counter()
    if freq:
        return freq
    
    # Fallback to psutil
    return _get_freq_psutil()


def _get_freq_performance_counter():
    """
    Use Windows Performance Counter to get actual live CPU frequency.
    Counter: \Processor Information(_Total)\% Processor Performance
    Returns percentage of base frequency (can exceed 100% with turbo boost).
    """
    if not WIN32_AVAILABLE or _freq_base is None:
        return None
    
    query = None
    try:
        # Counter path - shows CPU performance as percentage of base
        counter_path = r'\Processor Information(_Total)\% Processor Performance'
        
        # Open query
        query = win32pdh.OpenQuery(None, 0)
        
        # Add counter
        counter_handle = win32pdh.AddEnglishCounter(query, counter_path, 0)
        
        # Collect first sample
        win32pdh.CollectQueryData(query)
        
        # Wait briefly for delta calculation
        time.sleep(0.1)
        
        # Collect second sample
        win32pdh.CollectQueryData(query)
        
        # Get the value
        counter_type, value = win32pdh.GetFormattedCounterValue(
            counter_handle, 
            win32pdh.PDH_FMT_DOUBLE
        )
        
        # Close query
        win32pdh.CloseQuery(query)
        
        # Calculate actual frequency
        # value is percentage (e.g., 150 means 150% of base)
        # _freq_base is in MHz
        if value > 0:
            actual_freq = _freq_base * (value / 100.0)
            return actual_freq
            
    except Exception:
        if query:
            try:
                win32pdh.CloseQuery(query)
            except:
                pass
    
    return None


def _get_freq_psutil():
    """Fallback: Use psutil (may be static on Windows)"""
    try:
        f = psutil.cpu_freq(percpu=False)
        if f and f.current and f.current > 0:
            return f.current
    except Exception:
        pass
    return None

if __name__ == "__main__":
    cpu_temp = get_cpu_temperature()
    def diagnose_cpu_freq():
        """Diagnostic function to see what data sources are available"""
        print("=== CPU FREQUENCY DIAGNOSTICS ===\n")
        
        # Check psutil
        print("1. Testing psutil.cpu_freq():")
        try:
            f = psutil.cpu_freq(percpu=False)
            if f:
                print(f"   Current: {f.current} MHz")
                print(f"   Min: {f.min} MHz")
                print(f"   Max: {f.max} MHz")
            else:
                print("   psutil returned None")
        except Exception as e:
            print(f"   Error: {e}")
        
        # Check WMI
        print("\n2. Testing WMI (MaxClockSpeed):")
        base = _get_base_frequency_wmi()
        print(f"   Base frequency: {base} MHz")
        
        # Check globals
        print("\n3. Current global state:")
        print(f"   _freq_base: {_freq_base}")
        print(f"   _freq_min: {_freq_min}")
        print(f"   _freq_max: {_freq_max}")
        print(f"   _last_freq: {_last_freq}")
        
        # Check if pywin32 is available
        print(f"\n4. pywin32 available: {WIN32_AVAILABLE}")
        
        # Try to get a live reading
        print("\n5. Testing live frequency read:")
        if WIN32_AVAILABLE and _freq_base:
            freq = _get_freq_performance_counter()
            print(f"   Performance Counter returned: {freq} MHz")
        else:
            print(f"   Cannot test (pywin32={WIN32_AVAILABLE}, base={_freq_base})")

    # Run it
    diagnose_cpu_freq()
    # Call this function to get CPU frequency data
    # current_ghz, min_ghz, max_ghz = get_cpu_freq(rate_limit_sec=1.0)

    # w = wmi.WMI(namespace="root\\wmi")
    # while True:
    #     for sensor in w.MSAcpi_ThermalZoneTemperature():
    #         temp_c = (sensor.CurrentTemperature / 10.0) - 273.15
    #         print(f"{sensor.InstanceName}: {temp_c:.1f} °C")
    #     print("-----")
    #     # Example usage:
    #     if current_ghz:
    #         print(f"Current CPU: {current_ghz} GHz")
    #         print(f"Min: {min_ghz} GHz")
    #         print(f"Max: {max_ghz} GHz")
    #     else:
    #         print("CPU frequency unavailable")
    #     time.sleep(2)
    # #if cpu_temp is not None:
    # # while cpu_temp is not None:
    # #     print(f"Current CPU Temperature: {cpu_temp:.2f}°C")
    # #     time.sleep(3)