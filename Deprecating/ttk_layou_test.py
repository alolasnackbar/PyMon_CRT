# ============= CRT_overlay ========================
import tkinter as tk
from ttkbootstrap import Style
from PIL import Image, ImageDraw, ImageTk, ImageFilter
import math

class CRTEffectOverlay:
    def __init__(self, parent,
                 scanline_spacing=3,
                 scanline_alpha=90,
                 scanline_color=(0, 255, 0),
                 vignette_strength=180,
                 vignette_blur=120,
                 barrel_strength=0.15,
                 enabled=True):
        self.parent = parent
        self.enabled = enabled
        
        # Create a transparent toplevel window overlay
        self.overlay_window = tk.Toplevel(parent)
        self.overlay_window.withdraw()  # Hide initially
        
        # Make it transparent and click-through
        self.overlay_window.attributes('-alpha', 1.0)  # Fully opaque window
        self.overlay_window.attributes('-topmost', True)  # Always on top
        self.overlay_window.overrideredirect(True)  # No window decorations
        
        # Make clicks pass through (Windows only - for Linux/Mac, canvas state='disabled' works)
        try:
            self.overlay_window.attributes('-transparentcolor', 'black')
        except tk.TclError:
            pass  # Not Windows
        
        # Canvas with black background (will be transparent on Windows)
        self.canvas = tk.Canvas(
            self.overlay_window, 
            highlightthickness=0, 
            bd=0,
            bg='black'
        )
        self.canvas.pack(fill='both', expand=True)
        
        self._tk_image = None
        self._last_size = (0, 0)

        # parameters
        self.scanline_spacing = scanline_spacing
        self.scanline_alpha = scanline_alpha
        self.scanline_color = scanline_color
        self.vignette_strength = vignette_strength
        self.vignette_blur = vignette_blur
        self.barrel_strength = barrel_strength

        # debounce resize
        self._after_id = None
        
        # Bind to parent window events
        parent.bind("<Configure>", self._on_parent_configure)
        parent.bind("<Map>", self._on_parent_map)
        parent.bind("<Unmap>", self._on_parent_unmap)
        
        # Show if enabled
        if self.enabled:
            self._sync_geometry()
            self.overlay_window.deiconify()

    def _on_parent_configure(self, event):
        """Sync overlay position and size with parent window"""
        if event.widget != self.parent:
            return
            
        if self._after_id:
            try:
                self.parent.after_cancel(self._after_id)
            except Exception:
                pass
        self._after_id = self.parent.after(50, self._sync_and_update)

    def _on_parent_map(self, event):
        """Show overlay when parent is shown"""
        if self.enabled:
            self.overlay_window.deiconify()

    def _on_parent_unmap(self, event):
        """Hide overlay when parent is hidden"""
        self.overlay_window.withdraw()

    def _sync_geometry(self):
        """Synchronize overlay window geometry with parent window"""
        self.parent.update_idletasks()
        x = self.parent.winfo_x()
        y = self.parent.winfo_y()
        w = self.parent.winfo_width()
        h = self.parent.winfo_height()
        
        self.overlay_window.geometry(f"{w}x{h}+{x}+{y}")
        return w, h

    def _sync_and_update(self):
        """Sync geometry and update overlay"""
        self._after_id = None
        w, h = self._sync_geometry()
        
        if (w, h) == self._last_size or w < 2 or h < 2:
            return
        self._last_size = (w, h)
        
        self._update_overlay()

    def _update_overlay(self):
        """Update the CRT overlay image"""
        w, h = self._last_size
        if w < 2 or h < 2:
            return

        img = self._create_crt_image(w, h)
        self._tk_image = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self._tk_image)

    def _create_crt_image(self, w, h):
        """Create CRT effect image with transparency"""
        # Start with fully transparent image
        base = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(base)
        r, g, b = self.scanline_color

        # Draw scanlines
        for y in range(0, h, self.scanline_spacing):
            draw.line((0, y, w, y), fill=(r, g, b, self.scanline_alpha))

        # Draw subtle glow lines
        glow_alpha = max(5, int(self.scanline_alpha * 0.1))
        for y in range(0, h, self.scanline_spacing):
            if y + 1 < h:
                draw.line((0, y + 1, w, y + 1), fill=(r, g, b, glow_alpha))

        # Create vignette effect
        if self.vignette_strength > 0:
            mask = Image.new("L", (w, h), 0)
            mdraw = ImageDraw.Draw(mask)
            inset_x, inset_y = int(w * 0.08), int(h * 0.08)
            mdraw.ellipse((inset_x, inset_y, w - inset_x, h - inset_y), fill=255)
            mask = mask.filter(ImageFilter.GaussianBlur(radius=self.vignette_blur))
            mask_inv = Image.eval(mask, lambda px: 255 - px)

            dark = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            mask_strength = mask_inv.point(lambda px: int(px * (self.vignette_strength / 255.0)))
            dark.paste((0, 0, 0, 255), (0, 0), mask_strength)
            base = Image.alpha_composite(base, dark)

        # Add subtle edge color fringing
        edge = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ed = ImageDraw.Draw(edge)
        t = max(2, int(min(w, h) * 0.008))
        ed.rectangle((0, 0, t, h), fill=(30, 0, 0, 14))
        ed.rectangle((w - t, 0, w, h), fill=(0, 20, 40, 14))
        base = Image.alpha_composite(base, edge)

        # Optional barrel distortion (expensive, disabled by default)
        if self.barrel_strength > 0:
            base = self._apply_barrel_distortion(base)

        return base

    def _apply_barrel_distortion(self, img):
        """Apply barrel distortion effect (CPU intensive)"""
        w, h = img.size
        k = self.barrel_strength

        src = img.convert("RGBA")
        dest = Image.new("RGBA", (w, h), (0, 0, 0, 0))

        cx, cy = w / 2, h / 2
        for y in range(h):
            for x in range(w):
                nx = (x - cx) / cx
                ny = (y - cy) / cy
                r = math.sqrt(nx * nx + ny * ny)
                if r == 0:
                    scale = 1
                else:
                    scale = 1 / (1 + k * (r ** 2))
                sx = int(cx + nx * cx * scale)
                sy = int(cy + ny * cy * scale)
                if 0 <= sx < w and 0 <= sy < h:
                    dest.putpixel((x, y), src.getpixel((sx, sy)))

        return dest
    
    def toggle_visibility(self):
        """Toggle CRT effect on/off"""
        if self.overlay_window.winfo_ismapped():
            self.overlay_window.withdraw()
            self.enabled = False
        else:
            self._sync_geometry()
            self.overlay_window.deiconify()
            self.enabled = True
            self._update_overlay()

    def destroy(self):
        """Clean up the overlay"""
        try:
            self.overlay_window.destroy()
        except:
            pass


def integrate_crt_overlay(root, config=None):
    """
    Integrate CRT overlay effect into the GUI.
    Call this function after widgets are built but before starting mainloop.
    
    Args:
        root: The tkinter root window
        config: Optional dict with CRT settings. If None, uses defaults.
                Available keys: scanline_spacing, scanline_alpha, scanline_color,
                               vignette_strength, vignette_blur, barrel_strength, enabled
    
    Returns:
        CRTEffectOverlay object for later control
    """
    # Default settings - subtle effect that matches your green theme
    default_config = {
        'scanline_spacing': 3,
        'scanline_alpha': 40,           # Lower for more subtle effect
        'scanline_color': (0, 255, 70),
        'vignette_strength': 100,       # Reduced for subtlety
        'vignette_blur': 100,
        'barrel_strength': 0,           # Disabled by default for performance
        'enabled': True
    }
    
    # Merge user config with defaults
    if config:
        default_config.update(config)
    
    # Create CRT overlay
    crt_overlay = CRTEffectOverlay(root, **default_config)
    
    # Initial update after a delay
    root.after(300, crt_overlay._update_overlay)
    return crt_overlay



    
