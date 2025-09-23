# --- Widget ---
MAX_POINTS = 60
REFRESH_MS = 1000
DISK_IO_MAX_MBPS = 500
GRAPH_HEIGHT = 90
PROGRESS_THICKNESS = 24
CRT_LINE_SMOT = 69

# Color schemes for color blind mode
CRT_GREEN = "#00FF66"
CRT_YELLOW = "#FFFF00"
CRT_RED = "#FF4444"
CRT_GRID  = "#024D02"
CRT_CYAN = "#04AD97"

COLORBLIND_COLORS = {
    'success': '#0173B2',   # Blue
    'warning': '#DE8F05',   # Orange  
    'danger': '#CC78BC',    # Pink
    'info': '#029E73'       # Teal
}

NORMAL_COLORS = {
    'success': CRT_GREEN,
    'warning': CRT_YELLOW, 
    'danger': CRT_RED,
    'info': CRT_CYAN
}

# --- Font styling ---
FONT_TITLE = ("Consolas", 14, "bold")
FONT_SYSTIME = ("Consolas", 55, "bold")
FONT_INFOTXT = ("Consolas", 11, "bold")
FONT_NETTXT = ("Consolas", 20, "bold")

FONT_TAB_TITLE_COLOR = "success"
FONT_OVERLAY = ('Helvetica', 12)
FONT_INFO = ("Consolas")

# --- Constants & Globals ---
REFRESH_GUI_MS = 100
REFRESH_HEAVY_MS = REFRESH_MS * 5
REFRESH_SLOW_MS = REFRESH_MS * 2

NETWORK_INTERFACE = None
PING_HOST = "8.8.8.8"
PING_COUNT = 3