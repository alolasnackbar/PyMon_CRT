# image_viewer.py
import tkinter as tk
from PIL import Image, ImageTk
import os

def show_image(image_path, title="Image Viewer", bg_color='#000000', info_color='#00FF00', 
               auto_close=False, close_delay=3000):
    """
    Opens an image in a window sized to fit the image dimensions.
    CRT-themed to match your app.
    
    Args:
        image_path (str): Path to the image file
        title (str): Window title
        bg_color (str): Background color (default: black)
        info_color (str): Info text color (default: CRT green)
        auto_close (bool): Automatically close after delay (default: False)
        close_delay (int): Delay before auto-close in milliseconds (default: 3000ms = 3s)
    """
    if not os.path.exists(image_path):
        print(f"Error: Image not found at {image_path}")
        return False
    
    try:
        # Load image
        original_img = Image.open(image_path)
        img_width, img_height = original_img.size
        
        # Get screen dimensions
        temp = tk.Tk()
        screen_width = temp.winfo_screenwidth()
        screen_height = temp.winfo_screenheight()
        temp.destroy()
        
        # Calculate window size (90% of screen max)
        max_width = int(screen_width * 0.9)
        max_height = int(screen_height * 0.9) - 50  # Reserve space for info bar
        
        # Scale if needed
        display_img = original_img
        new_width, new_height = img_width, img_height
        
        if img_width > max_width or img_height > max_height:
            ratio = min(max_width / img_width, max_height / img_height)
            new_width = int(img_width * ratio)
            new_height = int(img_height * ratio)
            display_img = original_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Create window
        window = tk.Tk()
        window.title(f"{title} - {os.path.basename(image_path)}")
        window.configure(bg=bg_color)
        window.resizable(False, False)
        
        # Convert image
        photo = ImageTk.PhotoImage(display_img)
        
        # Display image
        image_label = tk.Label(window, image=photo, borderwidth=0, bg=bg_color)
        image_label.image = photo  # Keep reference
        image_label.pack(fill=tk.BOTH, expand=True)
        
        # Info bar with countdown if auto-close is enabled
        info_text = f"[{os.path.basename(image_path)}] {img_width}x{img_height}px"
        if new_width != img_width or new_height != img_height:
            info_text += f" (scaled to {new_width}x{new_height})"
        
        if auto_close:
            info_text += f" | Closing in {close_delay//1000}s..."
        else:
            info_text += " | Press ESC or Q to close"
        
        info_label = tk.Label(
            window,
            text=info_text,
            fg=info_color,
            bg=bg_color,
            font=('Courier', 9),
            anchor='w',
            padx=10,
            pady=5
        )
        info_label.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Countdown timer (if auto-close)
        if auto_close:
            countdown_seconds = close_delay // 1000
            
            def update_countdown(remaining):
                if remaining > 0:
                    # Update info text with countdown
                    countdown_text = f"[{os.path.basename(image_path)}] {img_width}x{img_height}px"
                    if new_width != img_width or new_height != img_height:
                        countdown_text += f" (scaled to {new_width}x{new_height})"
                    countdown_text += f" | Closing in {remaining}s... (press any key to cancel)"
                    info_label.config(text=countdown_text)
                    window.after(1000, lambda: update_countdown(remaining - 1))
                else:
                    window.destroy()
            
            # Start countdown
            window.after(100, lambda: update_countdown(countdown_seconds))
            
            # Cancel auto-close on any key press
            def cancel_close(event):
                window.unbind('<Key>')
                window.unbind('<Button-1>')
                info_label.config(text=f"[{os.path.basename(image_path)}] | Auto-close cancelled. Press ESC or Q to close")
            
            window.bind('<Key>', cancel_close)
            window.bind('<Button-1>', cancel_close)  # Cancel on mouse click too
        
        # Keybindings (always available)
        window.bind('<Escape>', lambda e: window.destroy())
        window.bind('q', lambda e: window.destroy())
        window.bind('Q', lambda e: window.destroy())
        
        # Set window size and center
        total_height = new_height + 40  # Image + info bar
        window.geometry(f"{new_width}x{total_height}")
        window.update_idletasks()
        
        x = (screen_width - new_width) // 2
        y = (screen_height - total_height) // 2
        window.geometry(f"{new_width}x{total_height}+{x}+{y}")
        
        # Focus window
        window.lift()
        window.focus_force()
        
        window.mainloop()
        return True
        
    except Exception as e:
        print(f"Error loading image: {e}")
        return False


def show_image_threaded(image_path, title="Image Viewer", auto_close=False, close_delay=3000):
    """
    Opens image in a separate thread to avoid blocking the main GUI.
    
    Args:
        image_path (str): Path to the image file
        title (str): Window title
        auto_close (bool): Automatically close after delay
        close_delay (int): Delay in milliseconds before closing
    """
    import threading
    
    thread = threading.Thread(
        target=show_image,
        args=(image_path, title),
        kwargs={'auto_close': auto_close, 'close_delay': close_delay},
        daemon=True
    )
    thread.start()


def flash_image(image_path, title="Notification", duration=2000):
    """
    Quickly flash an image on screen for a short duration.
    Convenience function for notifications.
    
    Args:
        image_path (str): Path to the image file
        title (str): Window title
        duration (int): How long to show image in milliseconds (default: 2000ms = 2s)
    """
    show_image_threaded(image_path, title, auto_close=True, close_delay=duration)


if __name__ == "__main__":
    # Test the viewer with auto-close
    show_image("nohead_test.png", "Test Viewer", auto_close=True, close_delay=1000)