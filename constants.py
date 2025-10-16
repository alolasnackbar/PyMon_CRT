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

# Color scheme for detection status
STATUS_COLORS = {
    'default': CRT_RED,      # Red: Default/undetected
    'detected': CRT_GREEN,   # Green: Values detected
    'missing': CRT_YELLOW,   # Yellow: Not supported/null values
    'loading': CRT_CYAN      # Cyan: Currently testing
}

# --- Font styling ---
FONT_TITLE = ("Consolas", 14, "bold")
FONT_SYSTIME = ("Consolas", 55, "bold")
FONT_INFOTXT = ("Consolas", 11, "bold")
FONT_NETTXT = ("Consolas", 17, "bold")
FONT_COFIG = ("Consolas", 9, "bold")
FONT_NOTEB = ("Consolas", 8, "bold")

FONT_TAB_TITLE_COLOR = "success"
FONT_OVERLAY = ('Helvetica', 12)
FONT_INFO = ("Consolas","bold")

# --- Constants & Globals ---
REFRESH_GUI_MS = 100
REFRESH_HEAVY_MS = REFRESH_MS * 5
REFRESH_SLOW_MS = REFRESH_MS * 2

NETWORK_INTERFACE = None
PING_HOST = "8.8.8.8"
PING_COUNT = 3

# Configuration defaults
DEFAULT_CONFIG = {
    "monitor_index": 3,
    "process_count": 5,
    "cycle_enabled": False,
    "cycle_delay": 5,
    "focus_enabled": True,
    "cpu_threshold": 80,
    "temp_threshold": 75,
    "latency_threshold": 200,
    "colorblind_mode": False
}

def configure_app_styles(style_obj):
    """
    Configure all custom styles for the application.
    Call this once after creating your tb.Style() object.
    """
    
    # ===== NOTEBOOK TABS =====
    style_obj.configure(
        'TNotebook.Tab',
        foreground=CRT_GREEN,      # Tab text color
        background='#1a1a1a',       # Tab background
        font=FONT_NOTEB,          # Your font constant
        padding=[10, 5]             # Padding for better look
    )
    
    style_obj.map(
        'TNotebook.Tab',
        foreground=[
            ('selected', '#FFFFFF'),    # White when selected
            ('!selected', CRT_GREEN)    # Green when not selected
        ],
        background=[
            ('selected', '#2d2d2d'),    # Darker when selected
            ('!selected', '#1a1a1a')    # Normal when not selected
        ]
    )

    # ===== BUTTONS =====
    style_obj.configure(
        'TButton',
        foreground=CRT_GREEN,
        background='#1a1a1a',
        font=FONT_NOTEB,
        borderwidth=1,
        focuscolor='none'
    )
    
    style_obj.map(
        'TButton',
        foreground=[
            ('pressed', '#FFFFFF'),
            ('active', '#FFFF00'),
            ('!disabled', CRT_GREEN)
        ],
        background=[
            ('pressed', '#0a0a0a'),
            ('active', '#2d2d2d')
        ]
    )
    
    # ===== CUSTOM CRT BUTTON STYLE =====
    style_obj.configure(
        'CRT.TButton',
        foreground=CRT_GREEN,
        font=FONT_NOTEB,
        borderwidth=2
    )
    
    style_obj.map(
        'CRT.TButton',
        foreground=[('active', '#FFFFFF')],
        background=[('active', '#1a1a1a')],
        bordercolor=[('active', '#FFFF00')]
    )
    
    # ===== LABELS =====
    style_obj.configure(
        'TLabel',
        foreground=CRT_GREEN,
        font=FONT_NOTEB
    )
    
    # # ===== FRAMES =====
    # style_obj.configure(
    #     'TFrame',
    #     background='#1a1a1a'
    # )
    
    # ===== LABELFRAMES =====
    style_obj.configure(
        'TLabelframe',
        foreground=CRT_GREEN,
        bordercolor=CRT_GREEN,
        borderwidth=1
    )
    
    style_obj.configure(
        'TLabelframe.Label',
        foreground=CRT_GREEN,
        font=FONT_NOTEB
    )
    
    # ===== CHECKBUTTONS =====
    style_obj.configure(
        'TCheckbutton',
        foreground=CRT_GREEN,
        font=FONT_NOTEB
    )
    
    # ===== RADIOBUTTONS =====
    style_obj.configure(
        'TRadiobutton',
        foreground=CRT_GREEN,
        font=FONT_NOTEB
    )
    
    # ===== ENTRY FIELDS =====
    style_obj.configure(
        'TEntry',
        foreground=CRT_GREEN,
        fieldbackground='#000000',
        insertcolor=CRT_GREEN
    )
    
    # ===== PROGRESSBARS =====
    style_obj.configure(
        'TProgressbar',
        troughcolor='#0a0a0a',
        background=CRT_GREEN,
        borderwidth=0,
        thickness=20
    )

    # ===== COMBOBOX =====
    style_obj.configure(
        'TCombobox',
        foreground=CRT_GREEN,
        fieldbackground='#000000',     # Dropdown field background
        background="#00FF66",          # Button background
        arrowcolor=CRT_GREEN,          # Dropdown arrow color
        selectbackground='#000000',    # Selected item background
        selectforeground=CRT_GREEN,    # Selected item text
        font=FONT_COFIG
    )
    
    style_obj.map(
        'TCombobox',
        fieldbackground=[('readonly', '#000000')],
        foreground=[('readonly', CRT_GREEN)],
        arrowcolor=[('active', '#FFFF00')]  # Yellow arrow on hover
    )
    
    # ===== SUCCESS OUTLINE BUTTONS (for your ping/config buttons) =====
    style_obj.configure(
        'success-outline.TButton',
        foreground=CRT_GREEN,
        background='#1a1a1a',
        bordercolor=CRT_GREEN,
        borderwidth=1,
        font=FONT_NOTEB
    )
    
    style_obj.map(
        'success-outline.TButton',
        foreground=[
            ('pressed', '#000000'),
            ('active', '#FFFFFF')
        ],
        background=[
            ('pressed', CRT_GREEN),
            ('active', '#2d2d2d')
        ],
        bordercolor=[('active', '#FFFF00')]
    )

     # ===== SPINBOX =====
    style_obj.configure(
        'TSpinbox',
        foreground=CRT_GREEN,
        fieldbackground='#000000',      # Text field background
        background=CRT_GREEN,           # Button background
        arrowcolor=CRT_GREEN,           # Up/down arrow color
        insertcolor=CRT_GREEN,          # Cursor color
        selectbackground='#2d2d2d',     # Selected text background
        selectforeground='#FFFFFF',     # Selected text color
        borderwidth=1,
        relief='solid',
        font=FONT_NOTEB
    )
    
    style_obj.map(
        'TSpinbox',
        fieldbackground=[
            ('focus', '#0a0a0a'),       # Slightly lighter when focused
            ('!disabled', '#000000')
        ],
        foreground=[
            ('disabled', '#555555'),
            ('!disabled', CRT_GREEN)
        ],
        arrowcolor=[
            ('active', '#FFFF00'),      # Yellow arrows on hover
            ('pressed', '#FFFFFF'),     # White when clicked
            ('!disabled', CRT_GREEN)
        ],
        bordercolor=[
            ('focus', CRT_GREEN),       # Green border when focused
            ('!focus', '#2d2d2d')
        ]
    )
    
    print("✓ Custom styles cumfigured")