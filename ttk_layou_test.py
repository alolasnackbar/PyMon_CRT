import tkinter as tk
from ttkbootstrap import Window
from PIL import Image, ImageTk

# Create main window
app = Window(themename="superhero")
app.title("PNG Overlay Example")
app.geometry("960x600")

# ==============================================================================
# ==== Transparent PNG Overlay
# ==============================================================================
def create_transparent_overlay(root, image_path):
    """Creates a transparent PNG overlay that covers the entire window."""
    try:
        from PIL import Image, ImageTk
        
        # Create a top-level window for the overlay
        overlay = tk.Toplevel(root)
        overlay.withdraw()  # Hide initially
        
        # Make it transparent to mouse events (clicks pass through)
        overlay.overrideredirect(True)
        overlay.attributes('-topmost', True)
        overlay.attributes('-transparentcolor', 'black')  # Make black pixels transparent
        
        # Load and prepare the image
        img = Image.open(image_path)
        # Convert to RGBA if not already
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
            
        # Create a function to update overlay size and position
        def update_overlay():
            # Get root window geometry
            root.update_idletasks()
            x = root.winfo_x()
            y = root.winfo_y()
            width = root.winfo_width()
            height = root.winfo_height()
            
            # Resize image to match window size
            resized_img = img.resize((width, height), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(resized_img)
            
            # Update overlay
            overlay.geometry(f"{width}x{height}+{x}+{y}")
            
            # Clear and update the overlay canvas
            overlay_canvas = getattr(overlay, 'canvas', None)
            if overlay_canvas:
                overlay_canvas.delete("all")
                overlay_canvas.config(width=width, height=height)
                overlay_canvas.create_image(width//2, height//2, image=photo, anchor="center")
                overlay_canvas.image = photo  # Keep a reference
            else:
                # Create canvas if it doesn't exist
                overlay_canvas = tk.Canvas(overlay, width=width, height=height, 
                                         highlightthickness=0, bg='black')
                overlay_canvas.pack(fill='both', expand=True)
                overlay_canvas.create_image(width//2, height//2, image=photo, anchor="center")
                overlay_canvas.image = photo
                overlay.canvas = overlay_canvas
            
            overlay.deiconify()  # Show the overlay
        
        # Bind window events to update overlay
        def on_configure(event):
            if event.widget == root:
                root.after(10, update_overlay)  # Small delay to avoid excessive updates
                
        root.bind('<Configure>', on_configure)
        root.bind('<Map>', lambda e: root.after(10, update_overlay))
        
        # Initial overlay setup
        root.after(100, update_overlay)
        
        return overlay
        
    except ImportError:
        print("PIL (Pillow) not installed. Overlay disabled.")
        return None
    except Exception as e:
        print(f"Error creating overlay: {e}")
        return None

# Create the overlay (place this after style = tb.Style())
overlay_window = create_transparent_overlay(app, "Crt_overlay.png")  # Replace with your PNG path


app.mainloop()
