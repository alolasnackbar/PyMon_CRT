# REQUIRED DEPENDECY CHECK
-psutils
-ttkbootstrap
-wmi (cache)

# version 0.0.35 as of last updated
-cleaned main gui and split sections for tabs
-constants, crt_graphics, widgets as their own
-update monitor_core.py accordingly as of last 0.0.3

## ==== Feature to do list ======
1. bar still looks dodo find a way to make it seamelss (RAM)
2. Sizing constraints and readability fine tuning
3. network usage? average latency?
4. terminal logging for random stuff

EXAMPLE FOR FORMATING IN README
# A first-level heading
## A second-level heading
### A third-level heading


# use for batch style setup for dependcy
import sys
import subprocess

def install_and_import(package, import_name=None):
    import importlib
    try:
        importlib.import_module(import_name or package)
    except ImportError:
        print(f"Installing missing package: {package}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        importlib.invalidate_caches()
        importlib.import_module(import_name or package)

# Check/install ttkbootstrap
install_and_import("ttkbootstrap")
# Check/install psutil (if used in monitor_core)
try:
    import monitor_core
except ImportError:
    print("Missing required module: monitor_core. Please ensure it is present in your project directory.")
    sys.exit(1)
else:
    try:
        import psutil
    except ImportError:
        install_and_import("psutil")

# Now import everything else
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import monitor_core as core

# ...rest of your code...
