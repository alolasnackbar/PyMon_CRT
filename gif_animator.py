from tkinter import PhotoImage

def load_gif_frames(path):
    frames = []
    idx = 0
    while True:
        try:
            frame = PhotoImage(file=path, format=f"gif -index {idx}")
            frames.append(frame)
            idx += 1
        except Exception:
            break
    return frames

def animate_gif(label, frames, root, delay=100, idx=0):
    if frames:
        label.config(image=frames[idx])
        next_idx = (idx + 1) % len(frames)
        root.after(delay, animate_gif, label, frames, root, delay, next_idx)