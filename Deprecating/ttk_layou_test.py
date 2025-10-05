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
            # Try psutil first
            try:
                f = psutil.cpu_freq(percpu=False)
                if f:
                    # Note: min might be 0, so we check > 0
                    if f.min and f.min > 0:
                        _freq_min = round(f.min / 1000.0, 2)
                    if f.max and f.max > 0:
                        _freq_max = round(f.max / 1000.0, 2)
                        _freq_base = f.max  # Keep in MHz for calculations
            except Exception:
                pass
            
            # If we don't have base from psutil, get it from WMI
            if _freq_base is None:
                wmi_freq = _get_base_frequency_wmi()
                if wmi_freq and wmi_freq > 0:
                    _freq_base = wmi_freq
                    # Also set max if we don't have it
                    if _freq_max is None:
                        _freq_max = round(wmi_freq / 1000.0, 2)
            
            # Last resort: use current frequency as base
            if _freq_base is None:
                try:
                    f = psutil.cpu_freq(percpu=False)
                    if f and f.current and f.current > 0:
                        _freq_base = f.current
                        if _freq_max is None:
                            _freq_max = round(f.current / 1000.0, 2)
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
    Counter: \\Processor Information(_Total)\\% Processor Performance
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


def get_internal_state():
    """
    Helper function to inspect internal state for debugging.
    Returns dict with all global cache variables.
    """
    return {
        'freq_base_mhz': _freq_base,
        'freq_min_ghz': _freq_min,
        'freq_max_ghz': _freq_max,
        'last_freq_ghz': _last_freq,
        'last_check_timestamp': _last_freq_check,
        'win32_available': WIN32_AVAILABLE
    }
current, min_freq, max_freq = get_cpu_freq(rate_limit_sec=0.5)


print("Monitoring CPU frequency (Ctrl+C to stop)...")
print("-" * 50)

try:
    while True:
        current, min_freq, max_freq = get_cpu_freq(rate_limit_sec=0.5)
        
        if current and max_freq:
            # Calculate turbo boost percentage
            turbo_pct = ((current - max_freq) / max_freq) * 100
            turbo_indicator = "🔥" if turbo_pct > 5 else "⚡" if turbo_pct > 0 else "💤"
            
            print(f"{turbo_indicator} CPU: {current:.2f} GHz | "
                  f"Base: {max_freq} GHz | "
                  f"Turbo: {turbo_pct:+.1f}%", end='\r')
        else:
            print("CPU frequency unavailable", end='\r')
        
        time.sleep(1.0)
        
except KeyboardInterrupt:
    print("\nMonitoring stopped.")