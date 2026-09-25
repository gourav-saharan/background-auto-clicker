# -*- coding: utf-8 -*-
"""Ultimate Background Clicker (Multi-Target) — fixed build."""

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
    import ctypes
    from ctypes import windll
    HAS_WIN32 = True

    # Enable DPI awareness so coordinates match actual screen pixels
    try:
        windll.user32.SetProcessDPIAware()
    except Exception:
        pass
except ImportError:
    HAS_WIN32 = False


def get_base_dir():
    """Return the directory where the exe or script lives."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_dir()


class ClickTarget:
    """Holds all state for a single click target."""
    _next_id = 1

    def __init__(self, target_id=None, window_title=None, template_path=None):
        if target_id is not None:
            self.id = target_id
            ClickTarget._next_id = max(ClickTarget._next_id, target_id + 1)
        else:
            self.id = ClickTarget._next_id
            ClickTarget._next_id += 1

        self.window_title = window_title
        self.template_path = template_path or f"target_{self.id}.png"
        self.template_img = None
        self.target_hwnd = None
        self.click_count = 0
        self.enabled = True
        self.status = "Not Set"
        self._miss_count = 0
        self._min_log_count = 0

    def _abs_template_path(self):
        """Return the absolute path to the template image."""
        if os.path.isabs(self.template_path):
            return self.template_path
        return os.path.join(BASE_DIR, self.template_path)

    def load_template(self):
        """Load the template image from disk."""
        path = self._abs_template_path()
        if path and os.path.exists(path):
            self.template_img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            return self.template_img is not None
        return False

    def is_ready(self):
        """Check if this target is fully configured and ready to scan."""
        return self.window_title is not None and self.template_img is not None


class AutoClickerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Ultimate Background Clicker (Multi-Target)")
        self.root.geometry("620x720")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2b2d30")

        self.is_clicking = False
        self.running = True
        self.targets = []  # list of ClickTarget
        self.targets_lock = threading.Lock()  # protects self.targets
        self.config_path = os.path.join(BASE_DIR, "config.json")

        self.setup_styles()
        self.setup_ui()
        self.load_config()

        self.thread = threading.Thread(target=self.clicker_loop, daemon=True)
        self.thread.start()

        try:
            # Wrap hotkey callbacks in threads so they don't block the keyboard listener
            keyboard.add_hotkey('f8', lambda: threading.Thread(target=self.capture_target, daemon=True).start())
            keyboard.add_hotkey('f9', lambda: self.root.after(0, self.toggle_clicking))
        except Exception as e:
            self.log(f"WARNING: Could not bind hotkeys. Error: {e}")

    # ─── Styles ────────────────────────────────────────────────

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Dark.Treeview",
                         background="#1e1f22",
                         foreground="#a9b7c6",
                         fieldbackground="#1e1f22",
                         font=("Segoe UI", 9),
                         rowheight=28)
        style.configure("Dark.Treeview.Heading",
                         background="#3c3f41",
                         foreground="#a9b7c6",
                         font=("Segoe UI", 9, "bold"),
                         relief="flat")
        style.map("Dark.Treeview",
                   background=[("selected", "#2d5377")],
                   foreground=[("selected", "#ffffff")])
        style.map("Dark.Treeview.Heading",
                   background=[("active", "#4c5052")])
        style.configure("Dark.Horizontal.TScale",
                         background="#2b2d30",
                         troughcolor="#3c3f41",
                         sliderthickness=16)

    # ─── UI Layout ─────────────────────────────────────────────

    def setup_ui(self):
        bg = "#2b2d30"
        fg = "#a9b7c6"
        accent = "#3592c4"
        ok = "#589df6"

        tk.Label(self.root, text="Ultimate Background Clicker (Multi-Target)",
                 font=("Segoe UI", 14, "bold"), bg=bg, fg=accent).pack(pady=(10, 5))
        tk.Label(self.root,
                 text="Works fully in background \u2014 no need to keep target windows visible",
                 font=("Segoe UI", 9), bg=bg, fg="#6a737d").pack(pady=(0, 8))

        # ── Target List ──
        target_frame = tk.LabelFrame(self.root, text="Configured Targets",
                                      bg=bg, fg=fg, font=("Segoe UI", 10))
        target_frame.pack(fill=tk.X, padx=15, pady=5)

        cols = ("id", "window", "status", "clicks")
        self.tree = ttk.Treeview(target_frame, columns=cols, show="headings",
                                  height=5, style="Dark.Treeview")
        self.tree.heading("id", text="#")
        self.tree.heading("window", text="Window Title")
        self.tree.heading("status", text="Status")
        self.tree.heading("clicks", text="Clicks")
        self.tree.column("id", width=35, anchor="center", stretch=False)
        self.tree.column("window", width=300, anchor="w")
        self.tree.column("status", width=130, anchor="center")
        self.tree.column("clicks", width=60, anchor="center", stretch=False)
        self.tree.pack(fill=tk.X, padx=5, pady=(5, 2))

        self.empty_label = tk.Label(target_frame,
                                     text="No targets configured. Hover over a button and press F8 to add one.",
                                     bg="#1e1f22", fg="#6a737d",
                                     font=("Segoe UI", 9, "italic"), pady=10)

        btn_row = tk.Frame(target_frame, bg=bg)
        btn_row.pack(fill=tk.X, padx=5, pady=(2, 8))

        tk.Button(btn_row, text="+ Add Target (F8)",
                  command=lambda: threading.Thread(target=self.capture_target, daemon=True).start(),
                  bg="#365a3a", fg="white", font=("Segoe UI", 9, "bold"),
                  relief=tk.FLAT, padx=12, pady=4).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(btn_row, text="X Remove Selected",
                  command=self.remove_selected_target,
                  bg="#5a3636", fg="white", font=("Segoe UI", 9, "bold"),
                  relief=tk.FLAT, padx=12, pady=4).pack(side=tk.LEFT)

        tk.Button(btn_row, text="Recapture Selected",
                  command=lambda: threading.Thread(target=self.recapture_selected, daemon=True).start(),
                  bg="#4a4a36", fg="white", font=("Segoe UI", 9, "bold"),
                  relief=tk.FLAT, padx=12, pady=4).pack(side=tk.LEFT, padx=(8, 0))

        # ── Click Settings ──
        ctrl = tk.LabelFrame(self.root, text="Click Settings",
                              bg=bg, fg=fg, font=("Segoe UI", 10))
        ctrl.pack(fill=tk.X, padx=15, pady=5)

        tk.Label(ctrl, text="Scan/Click Interval (seconds):",
                 bg=bg, fg=fg).pack(side=tk.LEFT, padx=10, pady=10)

        self.interval_var = tk.DoubleVar(value=1.0)
        self.interval_slider = ttk.Scale(ctrl, from_=0.1, to=5.0,
                                          variable=self.interval_var,
                                          orient=tk.HORIZONTAL, length=150,
                                          style="Dark.Horizontal.TScale")
        self.interval_slider.pack(side=tk.LEFT, padx=10, pady=10)

        self.interval_label = tk.Label(ctrl, text="1.0s", bg=bg, fg=ok, width=5)
        self.interval_label.pack(side=tk.LEFT, padx=5, pady=10)
        self.interval_slider.bind("<B1-Motion>",
                                   lambda e: self.interval_label.config(text=f"{self.interval_var.get():.1f}s"))

        # ── Live Log ──
        log_frame = tk.LabelFrame(self.root, text="Live Vision & Activity Log",
                                   bg=bg, fg=fg, font=("Segoe UI", 10))
        log_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        self.log_area = scrolledtext.ScrolledText(log_frame, height=8,
                                                    bg="#1e1f22", fg="#a9b7c6",
                                                    font=("Consolas", 9), borderwidth=0)
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.log_area.config(state=tk.DISABLED)

        # ── Stats & Controls ──
        self.stats_label = tk.Label(self.root,
                                     text="Total Successful Clicks: 0  |  Active Targets: 0",
                                     font=("Segoe UI", 11, "bold"), bg=bg, fg=ok)
        self.stats_label.pack(pady=5)

        bf = tk.Frame(self.root, bg=bg)
        bf.pack(pady=10)
        self.toggle_btn = tk.Button(bf, text="START ALL (F9)",
                                     command=self.toggle_clicking,
                                     width=22, height=2, bg=ok, fg="white",
                                     font=("Segoe UI", 10, "bold"),
                                     relief=tk.FLAT, borderwidth=0)
        self.toggle_btn.pack(side=tk.TOP, padx=5)

        self.update_empty_label()

    # ─── Treeview Helpers ──────────────────────────────────────

    def refresh_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        with self.targets_lock:
            for t in self.targets:
                self.tree.insert("", "end", iid=str(t.id),
                                  values=(t.id, t.window_title or "(not set)",
                                          t.status, t.click_count))
        self.update_empty_label()
        self.update_stats()

    def update_target_row(self, target):
        iid = str(target.id)
        try:
            if self.tree.exists(iid):
                self.tree.item(iid, values=(target.id, target.window_title or "(not set)",
                                             target.status, target.click_count))
            else:
                self.tree.insert("", "end", iid=iid,
                                  values=(target.id, target.window_title or "(not set)",
                                          target.status, target.click_count))
        except tk.TclError:
            pass
        self.update_empty_label()

    def update_empty_label(self):
        if len(self.targets) == 0:
            self.empty_label.pack(fill=tk.X, padx=5, pady=5)
        else:
            self.empty_label.pack_forget()

    def update_stats(self):
        with self.targets_lock:
            total = sum(t.click_count for t in self.targets)
            active = sum(1 for t in self.targets if t.enabled and t.is_ready())
        self.stats_label.config(text=f"Total Successful Clicks: {total}  |  Active Targets: {active}")

    # ─── Logging ───────────────────────────────────────────────

    def log(self, message):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {message}\n"

        def _append():
            try:
                self.log_area.config(state=tk.NORMAL)
                self.log_area.insert(tk.END, line)
                n = int(self.log_area.index('end-1c').split('.')[0])
                if n > 500:
                    self.log_area.delete('1.0', '100.0')
                self.log_area.see(tk.END)
                self.log_area.config(state=tk.DISABLED)
            except tk.TclError:
                pass

        self.root.after(0, _append)

    # ─── Config Persistence ────────────────────────────────────

    def save_config(self):
        cfg = {"interval": self.interval_var.get(), "targets": []}
        with self.targets_lock:
            for t in self.targets:
                cfg["targets"].append({
                    "id": t.id,
                    "window_title": t.window_title,
                    "template": t.template_path
                })
        try:
            with open(self.config_path, "w") as f:
                json.dump(cfg, f, indent=2)
        except Exception as e:
            self.log(f"Error saving config: {e}")

    def load_config(self):
        if not os.path.exists(self.config_path):
            return
        try:
            with open(self.config_path, "r") as f:
                cfg = json.load(f)

            self.interval_var.set(cfg.get("interval", 1.0))
            self.interval_label.config(text=f"{self.interval_var.get():.1f}s")

            # Migrate old single-target format
            if "targets" not in cfg and "window_title" in cfg:
                old = cfg.get("window_title")
                if old:
                    t = ClickTarget(target_id=1, window_title=old,
                                    template_path="target_button.png")
                    if t.load_template():
                        t.status = "Loaded"
                        with self.targets_lock:
                            self.targets.append(t)
                        self.log(f"Migrated old target: {old}")
                        hwnd = self.find_hwnd_by_title(old)
                        if hwnd:
                            t.target_hwnd = hwnd
                            t.status = "Ready"
                        else:
                            t.status = "Window not found"
                    self.save_config()
                self.refresh_tree()
                return

            # Load multi-target format
            for entry in cfg.get("targets", []):
                t = ClickTarget(target_id=entry.get("id"),
                                window_title=entry.get("window_title"),
                                template_path=entry.get("template"))
                if t.load_template():
                    t.status = "Loaded"
                    with self.targets_lock:
                        self.targets.append(t)
                    self.log(f"Loaded target #{t.id}: {t.window_title}")
                    hwnd = self.find_hwnd_by_title(t.window_title)
                    if hwnd:
                        t.target_hwnd = hwnd
                        t.status = "Ready"
                    else:
                        t.status = "Window not found"
                        self.log(f"  Window not found right now.")
                else:
                    self.log(f"Skipped #{entry.get('id')}: template missing ({entry.get('template')})")

            self.refresh_tree()
        except Exception as e:
            self.log(f"Error loading config: {e}")

    # ─── Window Utilities ──────────────────────────────────────

    def find_hwnd_by_title(self, title):
        """Find a visible window whose title contains the given string."""
        if not HAS_WIN32:
            return None
        hwnds = []

        def cb(hwnd, _):
            try:
                if win32gui.IsWindowVisible(hwnd) and title in win32gui.GetWindowText(hwnd):
                    hwnds.append(hwnd)
            except Exception:
                pass

        win32gui.EnumWindows(cb, None)
        return hwnds[0] if hwnds else None

    def find_hwnd_by_title_any(self, title):
        """Find a window (visible OR minimized) whose title contains the given string."""
        if not HAS_WIN32:
            return None
        hwnds = []

        def cb(hwnd, _):
            try:
                wt = win32gui.GetWindowText(hwnd)
                if title in wt and (win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd)):
                    hwnds.append(hwnd)
            except Exception:
                pass

        win32gui.EnumWindows(cb, None)
        return hwnds[0] if hwnds else None

    # ─── Target Capture ────────────────────────────────────────

    def capture_target(self):
        """Capture a new target under the cursor (called from a worker thread)."""
        if not HAS_WIN32:
            self.log("ERROR: Win32 API not available.")
            return

        self.log("Move mouse to the target button... capturing in 1 second.")
        time.sleep(1.0)
        x, y = pyautogui.position()
        hwnd = win32gui.WindowFromPoint((x, y))

        if not hwnd:
            self.log("ERROR: No window found under mouse.")
            return

        # Walk to top-level parent
        parent = hwnd
        while win32gui.GetParent(parent) != 0:
            parent = win32gui.GetParent(parent)
        title = win32gui.GetWindowText(parent)

        target = ClickTarget(window_title=title)
        target.target_hwnd = parent

        # Clamp capture region to screen bounds
        sw, sh = pyautogui.size()
        rx = max(0, int(x - 60))
        ry = max(0, int(y - 25))
        rw = min(120, sw - rx)
        rh = min(50, sh - ry)

        try:
            shot = pyautogui.screenshot(region=(rx, ry, rw, rh))
            abs_path = os.path.join(BASE_DIR, target.template_path)
            shot.save(abs_path)
            target.template_img = cv2.imread(abs_path, cv2.IMREAD_GRAYSCALE)

            if target.template_img is None:
                self.log("ERROR: Failed to read captured image.")
                return

            target.status = "Ready"
            with self.targets_lock:
                self.targets.append(target)
            self.save_config()
            self.log(f"Target #{target.id} captured: '{title}'")
            self.root.after(0, self.refresh_tree)

        except Exception as e:
            self.log(f"Error capturing target: {e}")

    def recapture_selected(self):
        """Re-capture the button image for the selected target."""
        if not HAS_WIN32:
            return
        selected = self.tree.selection()
        if not selected:
            self.log("Select a target from the list first.")
            return

        tid = int(selected[0])
        with self.targets_lock:
            target = next((t for t in self.targets if t.id == tid), None)
        if not target:
            return

        self.log(f"Hover over the button for target #{target.id}... capturing in 1.5s.")
        time.sleep(1.5)

        x, y = pyautogui.position()
        hwnd = win32gui.WindowFromPoint((x, y))
        if not hwnd:
            self.log("ERROR: No window under mouse.")
            return

        parent = hwnd
        while win32gui.GetParent(parent) != 0:
            parent = win32gui.GetParent(parent)

        target.window_title = win32gui.GetWindowText(parent)
        target.target_hwnd = parent

        sw, sh = pyautogui.size()
        rx = max(0, int(x - 60))
        ry = max(0, int(y - 25))
        rw = min(120, sw - rx)
        rh = min(50, sh - ry)

        try:
            shot = pyautogui.screenshot(region=(rx, ry, rw, rh))
            abs_path = os.path.join(BASE_DIR, target.template_path)
            shot.save(abs_path)
            target.template_img = cv2.imread(abs_path, cv2.IMREAD_GRAYSCALE)
            target.status = "Ready"
            self.save_config()
            self.log(f"Target #{target.id} recaptured: '{target.window_title}'")
            self.root.after(0, self.refresh_tree)
        except Exception as e:
            self.log(f"Error recapturing: {e}")

    def remove_selected_target(self):
        selected = self.tree.selection()
        if not selected:
            self.log("Select a target from the list first.")
            return
        tid = int(selected[0])
        with self.targets_lock:
            self.targets = [t for t in self.targets if t.id != tid]
        self.save_config()
        self.refresh_tree()
        self.log(f"Removed target #{tid}.")

    # ─── Engine Toggle ─────────────────────────────────────────

    def toggle_clicking(self):
        with self.targets_lock:
            ready = [t for t in self.targets if t.is_ready()]
        if not ready:
            self.log("ERROR: No targets configured. Press F8 to capture at least one.")
            return

        self.is_clicking = not self.is_clicking
        if self.is_clicking:
            for t in ready:
                if t.target_hwnd is None or not win32gui.IsWindow(t.target_hwnd):
                    hwnd = self.find_hwnd_by_title_any(t.window_title)
                    if hwnd:
                        t.target_hwnd = hwnd
                        t.status = "Scanning..."
                    else:
                        t.status = "Window not found"
                        self.log(f"WARNING: #{t.id} window '{t.window_title}' not found.")
                else:
                    t.status = "Scanning..."

            self.log(f"Engine STARTED - scanning {len(ready)} target(s) in background...")
            self.toggle_btn.config(text="STOP ALL (F9)", bg="#c75450")
            self.refresh_tree()
        else:
            with self.targets_lock:
                for t in self.targets:
                    if t.is_ready():
                        t.status = "Stopped"
            self.log("Engine STOPPED.")
            self.toggle_btn.config(text="START ALL (F9)", bg="#589df6")
            self.refresh_tree()

    # ─── Background Window Capture ─────────────────────────────

    def capture_background_window(self, hwnd):
        """Capture a window's pixels using PrintWindow.

        Works for background windows. Minimized windows are skipped.
        Uses try/finally to ensure GDI resources are always released.
        """
        if not win32gui.IsWindow(hwnd):
            return None, 0, 0
        if win32gui.IsIconic(hwnd):
            return None, 0, 0

        hwndDC = None
        mfcDC = None
        saveDC = None
        saveBitMap = None

        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            width = right - left
            height = bottom - top
            if width <= 0 or height <= 0:
                return None, left, top

            hwndDC = win32gui.GetWindowDC(hwnd)
            mfcDC = win32ui.CreateDCFromHandle(hwndDC)
            saveDC = mfcDC.CreateCompatibleDC()

            saveBitMap = win32ui.CreateBitmap()
            saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
            saveDC.SelectObject(saveBitMap)

            # PW_RENDERFULLCONTENT = 2 — captures DWM/Electron/GPU windows
            windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 2)

            bmpinfo = saveBitMap.GetInfo()
            bmpstr = saveBitMap.GetBitmapBits(True)
            img = np.frombuffer(bmpstr, dtype='uint8').reshape(
                (bmpinfo['bmHeight'], bmpinfo['bmWidth'], 4))

            return img, left, top

        except Exception:
            return None, 0, 0

        finally:
            # Always release GDI resources
            try:
                if saveBitMap:
                    win32gui.DeleteObject(saveBitMap.GetHandle())
                if saveDC:
                    saveDC.DeleteDC()
                if mfcDC:
                    mfcDC.DeleteDC()
                if hwndDC and hwnd:
                    win32gui.ReleaseDC(hwnd, hwndDC)
            except Exception:
                pass

    # ─── Background Click Delivery ─────────────────────────────

    def _find_child_at_point(self, hwnd, screen_x, screen_y, depth=0):
        """Find the deepest child window at the given screen point (max 8 levels)."""
        if depth > 8:
            return hwnd
        try:
            cx, cy = win32gui.ScreenToClient(hwnd, (screen_x, screen_y))
            child = win32gui.ChildWindowFromPoint(hwnd, (cx, cy))
            if child and child != hwnd and win32gui.IsWindow(child):
                return self._find_child_at_point(child, screen_x, screen_y, depth + 1)
        except Exception:
            pass
        return hwnd

    def send_background_click(self, hwnd, match_x, match_y):
        """Send a virtual click at (match_x, match_y) in window-relative coordinates.

        Uses PostMessage so the real cursor is never moved.
        Locks foreground window to prevent focus theft.
        """
        try:
            win_left, win_top, _, _ = win32gui.GetWindowRect(hwnd)
            screen_x = win_left + match_x
            screen_y = win_top + match_y

            # Find the deepest child window within the target hierarchy
            target_wnd = self._find_child_at_point(hwnd, screen_x, screen_y)

            # Convert to client coordinates of the target window
            click_x, click_y = win32gui.ScreenToClient(target_wnd, (screen_x, screen_y))

            # Lock foreground to prevent focus theft during click
            try:
                # LSFW_LOCK = 1 — prevents other apps from stealing foreground
                windll.user32.LockSetForegroundWindow(1)
            except Exception:
                pass

            # Send the virtual click
            lparam = win32api.MAKELONG(click_x, click_y)
            win32gui.PostMessage(target_wnd, win32con.WM_LBUTTONDOWN,
                                 win32con.MK_LBUTTON, lparam)
            time.sleep(0.05)
            win32gui.PostMessage(target_wnd, win32con.WM_LBUTTONUP, 0, lparam)

            # Unlock foreground
            try:
                # LSFW_UNLOCK = 2
                windll.user32.LockSetForegroundWindow(2)
            except Exception:
                pass

            return True

        except Exception as e:
            self.log(f"Click delivery error: {e}")
            return False

    # ─── Per-Target Processing ─────────────────────────────────

    def process_target(self, target):
        """Run one scan+click cycle for a single target."""
        if not target.is_ready() or not target.enabled:
            return

        # Re-discover window handle if lost
        if target.target_hwnd is None or not win32gui.IsWindow(target.target_hwnd):
            hwnd = self.find_hwnd_by_title_any(target.window_title)
            if hwnd:
                target.target_hwnd = hwnd
            else:
                target.status = "Window not found"
                self.root.after(0, lambda t=target: self.update_target_row(t))
                return

        # Skip minimized windows silently
        if win32gui.IsIconic(target.target_hwnd):
            target.status = "Minimized (skipped)"
            target._min_log_count += 1
            if target._min_log_count % 20 == 1:
                self.log(f"#{target.id} Window is minimized. Keep it open (can be behind others).")
            self.root.after(0, lambda t=target: self.update_target_row(t))
            return

        try:
            # 1. Capture the background window
            bg_img, win_left, win_top = self.capture_background_window(target.target_hwnd)
            if bg_img is None:
                target.status = "Capture failed"
                self.root.after(0, lambda t=target: self.update_target_row(t))
                return

            # 2. Convert to grayscale
            gray = cv2.cvtColor(bg_img, cv2.COLOR_BGRA2GRAY)

            # 3. Template match
            th, tw = target.template_img.shape[:2]
            gh, gw = gray.shape[:2]

            # Ensure template fits inside captured image
            if tw > gw or th > gh:
                target.status = "Template too large"
                self.root.after(0, lambda t=target: self.update_target_row(t))
                return

            res = cv2.matchTemplate(gray, target.template_img, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)

            if max_val > 0.8:
                # Center of the matched button in window-relative coords
                mx = max_loc[0] + (tw // 2)
                my = max_loc[1] + (th // 2)

                if self.send_background_click(target.target_hwnd, mx, my):
                    target.click_count += 1
                    target.status = f"Matched ({max_val:.2f})"
                    self.log(f"#{target.id} MATCH ({max_val:.2f}) -> Clicked!")
                else:
                    target.status = "Click failed"
                    self.log(f"#{target.id} Match found but click delivery failed.")
            else:
                target.status = f"Scanning... ({max_val:.2f})"
                target._miss_count += 1
                if target._miss_count % 10 == 1:
                    self.log(f"#{target.id} Button not visible (best: {max_val:.2f}). Scanning...")

            self.root.after(0, lambda t=target: self.update_target_row(t))
            self.root.after(0, self.update_stats)

        except Exception as e:
            self.log(f"#{target.id} Error: {e}")
            target.status = "Error"
            self.root.after(0, lambda t=target: self.update_target_row(t))

    # ─── Main Clicker Loop ─────────────────────────────────────

    def clicker_loop(self):
        """Background thread: processes all targets each cycle."""
        while self.running:
            if self.is_clicking and HAS_WIN32:
                with self.targets_lock:
                    snapshot = list(self.targets)
                for t in snapshot:
                    if not self.is_clicking:
                        break
                    self.process_target(t)
                time.sleep(self.interval_var.get())
            else:
                time.sleep(0.1)

    # ─── Shutdown ──────────────────────────────────────────────

    def on_closing(self):
        self.running = False
        self.is_clicking = False
        self.save_config()
        try:
            keyboard.unhook_all()
        except Exception:
            pass
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
