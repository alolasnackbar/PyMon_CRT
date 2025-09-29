"""
Hardware Detection Diagnostic Tool
Tests all monitor_core.py functions and displays detection status
"""

import sys
import os
from datetime import datetime
import io

# Color codes for console output
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

class DiagnosticOutput:
    """Captures diagnostic output for display"""
    def __init__(self):
        self.output = []
        
    def write(self, text, color=None):
        """Write text with optional color"""
        self.output.append((text, color))
    
    def get_plain_text(self):
        """Get output as plain text without color codes"""
        return ''.join([text for text, _ in self.output])
    
    def get_colored_text(self):
        """Get output with color codes"""
        result = []
        for text, color in self.output:
            if color:
                result.append(f"{color}{text}{Colors.RESET}")
            else:
                result.append(text)
        return ''.join(result)

def run_diagnostics():
    """Run all diagnostic tests and return output"""
    output = DiagnosticOutput()
    
    # Header
    output.write("="*60 + "\n", Colors.CYAN)
    output.write("HARDWARE DETECTION DIAGNOSTIC\n", Colors.CYAN)
    output.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n", Colors.CYAN)
    output.write("="*60 + "\n\n", Colors.CYAN)
    
    # Module Check
    output.write("[MODULE DEPENDENCIES]\n", Colors.MAGENTA)
    output.write("-"*60 + "\n", Colors.WHITE)
    
    modules_required = ['psutil', 'subprocess', 'platform', 'time', 'shutil', 're', 'os', 'sys', 'datetime']
    modules_optional = ['wmi', 'json']
    
    all_available = True
    
    for module in modules_required:
        try:
            __import__(module)
            output.write(f"✓ {module:<20} [AVAILABLE]\n", Colors.GREEN)
        except ImportError:
            output.write(f"✗ {module:<20} [MISSING - CRITICAL]\n", Colors.RED)
            all_available = False
    
    for module in modules_optional:
        try:
            __import__(module)
            output.write(f"✓ {module:<20} [AVAILABLE]\n", Colors.GREEN)
        except ImportError:
            output.write(f"⚠ {module:<20} [MISSING - OPTIONAL]\n", Colors.YELLOW)
    
    if not all_available:
        output.write("\n⚠ WARNING: Missing critical modules!\n", Colors.RED)
        return output
    
    # Import monitor_core
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import monitor_core
    except ImportError as e:
        output.write(f"\n✗ Cannot import monitor_core.py: {e}\n", Colors.RED)
        return output
    
    # CPU Functions
    output.write("\n[CPU DETECTION]\n", Colors.MAGENTA)
    output.write("-"*60 + "\n", Colors.WHITE)
    
    try:
        usage = monitor_core.get_cpu_usage(interval=0.1)
        output.write(f"✓ CPU Usage: {usage}%\n", Colors.GREEN if usage > 0 else Colors.YELLOW)
        
        freq = monitor_core.get_cpu_freq()
        if freq and freq[0]:
            output.write(f"✓ CPU Frequency: {freq[0]} GHz\n", Colors.GREEN)
        else:
            output.write(f"⚠ CPU Frequency: Unavailable\n", Colors.YELLOW)
        
        info = monitor_core.get_cpu_info()
        if info.get('model') and info['model'] != "Unknown CPU":
            output.write(f"✓ CPU Model: {info['model']}\n", Colors.GREEN)
            output.write(f"  Cores: {info['physical_cores']}P/{info['logical_cores']}L\n", Colors.WHITE)
        else:
            output.write(f"⚠ CPU Model: Unknown\n", Colors.YELLOW)
        
        temp = monitor_core.get_cpu_temp()
        if temp:
            output.write(f"✓ CPU Temperature: {temp}°C\n", Colors.GREEN)
        else:
            output.write(f"✗ CPU Temperature: Not Available\n", Colors.RED)
    except Exception as e:
        output.write(f"✗ CPU Detection Error: {e}\n", Colors.RED)
    
    # Memory Functions
    output.write("\n[MEMORY DETECTION]\n", Colors.MAGENTA)
    output.write("-"*60 + "\n", Colors.WHITE)
    
    try:
        usage = monitor_core.get_ram_usage()
        output.write(f"✓ RAM Usage: {usage}%\n", Colors.GREEN)
        
        info = monitor_core.get_ram_info()
        output.write(f"✓ RAM: {info['used']}GB used / {info['available']}GB available\n", Colors.GREEN)
    except Exception as e:
        output.write(f"✗ Memory Detection Error: {e}\n", Colors.RED)
    
    # Disk Functions
    output.write("\n[DISK DETECTION]\n", Colors.MAGENTA)
    output.write("-"*60 + "\n", Colors.WHITE)
    
    try:
        read, write = monitor_core.get_disk_io()
        output.write(f"✓ Disk I/O: R:{read:.2f} MB/s W:{write:.2f} MB/s\n", Colors.GREEN)
        
        summary = monitor_core.get_disk_summary()
        if summary:
            output.write(f"✓ Disk Space: {summary}\n", Colors.GREEN)
        else:
            output.write(f"⚠ Disk Space: Unavailable\n", Colors.YELLOW)
    except Exception as e:
        output.write(f"✗ Disk Detection Error: {e}\n", Colors.RED)
    
    # GPU Functions
    output.write("\n[GPU DETECTION]\n", Colors.MAGENTA)
    output.write("-"*60 + "\n", Colors.WHITE)
    
    try:
        nvidia = monitor_core._nvidia_smi_available()
        amd = monitor_core._rocm_smi_available()
        
        if not nvidia and not amd:
            output.write(f"✗ GPU: Not detected (no nvidia-smi/rocm-smi)\n", Colors.RED)
        else:
            info = monitor_core.get_gpu_info()
            if info:
                output.write(f"✓ GPU: {info}\n", Colors.GREEN)
            
            usage = monitor_core.get_gpu_usage()
            if usage is not None:
                output.write(f"✓ GPU Usage: {usage}%\n", Colors.GREEN)
            else:
                output.write(f"⚠ GPU Usage: Unavailable\n", Colors.YELLOW)
            
            temp = monitor_core.get_gpu_temp()
            if temp is not None:
                output.write(f"✓ GPU Temperature: {temp}°C\n", Colors.GREEN)
            else:
                output.write(f"⚠ GPU Temperature: Unavailable\n", Colors.YELLOW)
    except Exception as e:
        output.write(f"✗ GPU Detection Error: {e}\n", Colors.RED)
    
    # Network Functions
    output.write("\n[NETWORK DETECTION]\n", Colors.MAGENTA)
    output.write("-"*60 + "\n", Colors.WHITE)
    
    try:
        interface = monitor_core.get_primary_interface()
        if interface:
            output.write(f"✓ Primary Interface: {interface}\n", Colors.GREEN)
            
            net_in, net_out, latency = monitor_core.net_usage_latency(interface=interface, ping_count=1)
            output.write(f"✓ Network I/O: In:{net_in} Out:{net_out} MB/s\n", Colors.GREEN)
            
            if latency:
                output.write(f"✓ Latency: {latency} ms\n", Colors.GREEN)
            else:
                output.write(f"⚠ Latency: Ping failed\n", Colors.YELLOW)
        else:
            output.write(f"✗ Network: No active interface\n", Colors.RED)
    except Exception as e:
        output.write(f"✗ Network Detection Error: {e}\n", Colors.RED)
    
    # Summary
    output.write("\n" + "="*60 + "\n", Colors.CYAN)
    output.write("DIAGNOSTIC COMPLETE\n", Colors.CYAN)
    output.write("="*60 + "\n", Colors.CYAN)
    
    return output

if __name__ == "__main__":
    # When run standalone, print colored output to console
    os.system('color' if os.name == 'nt' else '')
    
    result = run_diagnostics()
    print(result.get_colored_text())
    
    input("\nPress Enter to exit...")