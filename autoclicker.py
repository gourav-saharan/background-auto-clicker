import tkinter as tk
from tkinter import ttk, scrolledtext
import pyautogui
import threading
import time
import keyboard
import sys
import json
import os
import datetime
import cv2
import numpy as np

try:
    import win32gui
    import win32con
    import win32api
    import win32ui
    from ctypes import windll
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False
    

class AutoClickerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Ultimate Background Clicker")
        self.root.geometry("550x550")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2b2d30")
        
        self.is_clicking = False
        self.running = True
        self.click_count = 0
        self.config_path = "config.json"
        self.template_path = "target_button.png"
        
        self.target_hwnd = None
        self.window_title = None
        self.template_img = None
        
        self.setup_ui()
        self.load_config()
        
        self.thread = threading.Thread(target=self.clicker_loop, daemon=True)
        self.thread.start()
        
        try:
            keyboard.add_hotkey('f8', self.capture_target)
            keyboard.add_hotkey('f9', self.toggle_clicking)
        except Exception as e:
            self.log(f"WARNING: Could not bind hotkeys. Error: {e}")

    def setup_ui(self):
        bg_color = "#2b2d30"
        text_color = "#a9b7c6"
        accent_color = "#3592c4"
        success_color = "#589df6"
        
        tk.Label(self.root, text="Ultimate Background Clicker (Computer Vision)", font=("Segoe UI", 14, "bold"), bg=bg_color, fg=accent_color).pack(pady=10)
        
        target_frame = tk.LabelFrame(self.root, text="Target Configuration", bg=bg_color, fg=text_color, font=("Segoe UI", 10))
        target_frame.pack(fill=tk.X, padx=15, pady=5)
        
        tk.Label(target_frame, text="Hover over the RUN button and press F8 to capture it.", bg=bg_color, fg=text_color).pack(pady=5)
        
        self.target_status = tk.Label(target_frame, text="Status: Target Not Set", font=("Segoe UI", 10, "bold"), bg=bg_color, fg="#c75450")
        self.target_status.pack(pady=5)

        control_frame = tk.LabelFrame(self.root, text="Click Settings", bg=bg_color, fg=text_color, font=("Segoe UI", 10))
        control_frame.pack(fill=tk.X, padx=15, pady=5)
        
        tk.Label(control_frame, text="Scan/Click Interval (seconds):", bg=bg_color, fg=text_color).pack(side=tk.LEFT, padx=10, pady=10)
        
        self.interval_var = tk.DoubleVar(value=1.0)
        self.interval_slider = ttk.Scale(control_frame, from_=0.1, to=5.0, variable=self.interval_var, orient=tk.HORIZONTAL, length=150)
        self.interval_slider.pack(side=tk.LEFT, padx=10, pady=10)
        
        self.interval_label = tk.Label(control_frame, text="1.0s", bg=bg_color, fg=success_color, width=5)
        self.interval_label.pack(side=tk.LEFT, padx=5, pady=10)
        
        self.interval_slider.bind("<B1-Motion>", lambda e: self.interval_label.config(text=f"{self.interval_var.get():.1f}s"))
        
        log_frame = tk.LabelFrame(self.root, text="Live Vision & Activity Log", bg=bg_color, fg=text_color, font=("Segoe UI", 10))
        log_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)
        
        self.log_area = scrolledtext.ScrolledText(log_frame, height=10, bg="#1e1f22", fg="#a9b7c6", font=("Consolas", 9), borderwidth=0)
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.log_area.config(state=tk.DISABLED)
        
        self.stats_label = tk.Label(self.root, text="Total Successful Clicks: 0", font=("Segoe UI", 11, "bold"), bg=bg_color, fg=success_color)
        self.stats_label.pack(pady=5)
        
        btn_frame = tk.Frame(self.root, bg=bg_color)
        btn_frame.pack(pady=10)
        
        self.toggle_btn = tk.Button(btn_frame, text="START ENGINE (F9)", command=self.toggle_clicking, 
                                   width=20, height=2, bg=success_color, fg="white", 
                                   font=("Segoe UI", 10, "bold"), relief=tk.FLAT, borderwidth=0)
        self.toggle_btn.pack(side=tk.TOP, padx=5)

    def log(self, message):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {message}\n"
        self.log_area.config(state=tk.NORMAL)
        self.log_area.insert(tk.END, formatted)
        self.log_area.see(tk.END)
        self.log_area.config(state=tk.DISABLED)

    def save_config(self):
        config = {
            "window_title": self.window_title,
            "interval": self.interval_var.get()
        }
        with open(self.config_path, "w") as f:
            json.dump(config, f)

    def find_hwnd_by_title(self, title):
        if not HAS_WIN32: return None
        hwnds = []
        def enum_windows_proc(hwnd, lParam):
            if win32gui.IsWindowVisible(hwnd) and title in win32gui.GetWindowText(hwnd):
                hwnds.append(hwnd)
        win32gui.EnumWindows(enum_windows_proc, None)
        return hwnds[0] if hwnds else None

    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    config = json.load(f)
                
                self.window_title = config.get("window_title")
                self.interval_var.set(config.get("interval", 1.0))
                self.interval_label.config(text=f"{self.interval_var.get():.1f}s")
                
                if self.window_title and os.path.exists(self.template_path):
                    self.target_status.config(text=f"Loaded Target: '{self.window_title}'", fg="#589df6")
                    self.log(f"Profile loaded: {self.window_title}")
                    
                    self.template_img = cv2.imread(self.template_path, cv2.IMREAD_GRAYSCALE)
                    
                    hwnd = self.find_hwnd_by_title(self.window_title)
                    if hwnd:
                        self.target_hwnd = hwnd
                        self.log("Target window found automatically.")
                    else:
                        self.log("Target window not found right now. Will scan when started.")
            except Exception as e:
                self.log(f"Error loading config: {e}")

    def capture_target(self):
        if not HAS_WIN32: return
        time.sleep(0.5) # allow user to settle mouse
        x, y = pyautogui.position()
        hwnd = win32gui.WindowFromPoint((x, y))
        
        if hwnd:
            parent_hwnd = hwnd
            while win32gui.GetParent(parent_hwnd) != 0:
                parent_hwnd = win32gui.GetParent(parent_hwnd)
                
            self.window_title = win32gui.GetWindowText(parent_hwnd)
            self.target_hwnd = parent_hwnd
            
            # Capture the screen region
            region = (int(x - 60), int(y - 25), 120, 50)
            try:
                screenshot = pyautogui.screenshot(region=region)
                screenshot.save(self.template_path)
                self.template_img = cv2.imread(self.template_path, cv2.IMREAD_GRAYSCALE)
                
                self.target_status.config(text=f"Target Set: '{self.window_title}'", fg="#589df6")
                self.log(f"Captured Image! Target Window: {self.window_title}")
                self.save_config()
            except Exception as e:
                self.log(f"Error capturing image: {e}")
        else:
            self.log("ERROR: Failed to find window under mouse.")

    def toggle_clicking(self):
        if self.window_title is None or self.template_img is None:
            self.log("ERROR: You must capture a target first (Press F8).")
            return
            
        self.is_clicking = not self.is_clicking
        if self.is_clicking:
            self.log("Engine STARTED. Scanning background window...")
            self.toggle_btn.config(text="STOP ENGINE (F9)", bg="#c75450")
            
            if self.target_hwnd is None or not win32gui.IsWindow(self.target_hwnd):
                self.target_hwnd = self.find_hwnd_by_title(self.window_title)
                if not self.target_hwnd:
                    self.log(f"ERROR: Could not find window '{self.window_title}'.")
                    self.is_clicking = False
                    self.toggle_btn.config(text="START ENGINE (F9)", bg="#589df6")
        else:
            self.log("Engine STOPPED.")
            self.toggle_btn.config(text="START ENGINE (F9)", bg="#589df6")

    def capture_background_window(self, hwnd):
        # Captures hardware accelerated background windows
        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            width = right - left
            height = bottom - top
            if width <= 0 or height <= 0: return None, left, top

            hwndDC = win32gui.GetWindowDC(hwnd)
            mfcDC  = win32ui.CreateDCFromHandle(hwndDC)
            saveDC = mfcDC.CreateCompatibleDC()

            saveBitMap = win32ui.CreateBitmap()
            saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
            saveDC.SelectObject(saveBitMap)

            # PW_RENDERFULLCONTENT (2) allows capturing DWM/Electron background windows
            windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 2)

            bmpinfo = saveBitMap.GetInfo()
            bmpstr = saveBitMap.GetBitmapBits(True)

            img = np.frombuffer(bmpstr, dtype='uint8').reshape((bmpinfo['bmHeight'], bmpinfo['bmWidth'], 4))
            
            win32gui.DeleteObject(saveBitMap.GetHandle())
            saveDC.DeleteDC()
            mfcDC.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwndDC)
            
            return img, left, top
        except Exception as e:
            return None, 0, 0

    def clicker_loop(self):
        while self.running:
            if self.is_clicking and HAS_WIN32 and self.template_img is not None:
                if self.target_hwnd is None or not win32gui.IsWindow(self.target_hwnd):
                    self.log("WARNING: Target window lost! Waiting...")
                    self.target_hwnd = self.find_hwnd_by_title(self.window_title)
                    time.sleep(1)
                    continue
                
                try:
                    # 1. Capture the background window silently
                    bg_img, win_left, win_top = self.capture_background_window(self.target_hwnd)
                    
                    if bg_img is not None:
                        # 2. Convert to grayscale for matching
                        gray_bg = cv2.cvtColor(bg_img, cv2.COLOR_BGRA2GRAY)
                        
                        # 3. Search for the button image
                        res = cv2.matchTemplate(gray_bg, self.template_img, cv2.TM_CCOEFF_NORMED)
                        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
                        
                        if max_val > 0.8: # Found it!
                            t_h, t_w = self.template_img.shape
                            
                            # Center of the found button in Window Coordinates
                            match_x = max_loc[0] + (t_w // 2)
                            match_y = max_loc[1] + (t_h // 2)
                            
                            # Convert Window Coordinates -> Absolute Screen -> Client Area
                            abs_x = win_left + match_x
                            abs_y = win_top + match_y
                            
                            # Get correct child window under that point inside the parent
                            child_hwnd = win32gui.WindowFromPoint((abs_x, abs_y))
                            client_x, client_y = win32gui.ScreenToClient(child_hwnd, (abs_x, abs_y))
                            
                            # Send Virtual Click
                            lparam = win32api.MAKELONG(client_x, client_y)
                            win32gui.PostMessage(child_hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
                            time.sleep(0.05)
                            win32gui.PostMessage(child_hwnd, win32con.WM_LBUTTONUP, 0, lparam)
                            
                            self.click_count += 1
                            self.root.after(0, lambda: self.stats_label.config(text=f"Total Successful Clicks: {self.click_count}"))
                            self.log(f"VISUAL MATCH! (Confidence: {max_val:.2f}) -> Clicked button!")
                        else:
                            self.log("Button disappeared or not found. Skipping click.")
                            
                except Exception as e:
                    self.log(f"Engine loop error: {e}")
                    
                time.sleep(self.interval_var.get())
            else:
                time.sleep(0.1)

    def on_closing(self):
        self.running = False
        self.root.destroy()
        sys.exit(0)

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = AutoClickerApp(root)
        root.protocol("WM_DELETE_WINDOW", app.on_closing)
        root.mainloop()
    except KeyboardInterrupt:
        sys.exit(0)
