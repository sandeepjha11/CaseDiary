import subprocess
import os
import tkinter as tk
from PIL import Image, ImageTk
import time

# ✅ Splash screen
splash = tk.Tk()
splash.title("Launching Case Diary")
splash.geometry("400x300")
splash.overrideredirect(True)

try:
    logo = Image.open("logo.png").resize((200, 200))
    img = ImageTk.PhotoImage(logo)
    tk.Label(splash, image=img).pack(pady=10)
except:
    tk.Label(splash, text="📚 Case Diary", font=("Arial", 20)).pack(pady=40)

tk.Label(splash, text="Launching dashboard...", font=("Arial", 12)).pack()
splash.update()
time.sleep(2)
splash.destroy()

# ✅ Launch silently
script_path = os.path.join(os.path.dirname(__file__), "caseDiary.py")
subprocess.Popen(["streamlit", "run", script_path], creationflags=subprocess.CREATE_NO_WINDOW)