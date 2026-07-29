<h1 align="center">Ultimate Background Clicker</h1>

<p align="center">
  <b>A computer-vision auto-clicker for Windows that clicks buttons inside minimized or background windows — without ever moving your mouse.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-Windows-0078D6?logo=windows&logoColor=white" alt="Platform: Windows">
  <img src="https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/OpenCV-Vision-5C3EE8?logo=opencv&logoColor=white" alt="OpenCV">
  <img src="https://img.shields.io/badge/GUI-Tkinter-FF6F00" alt="Tkinter">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License: MIT">
</p>

---

A Windows auto-clicker that uses **computer vision** to find and click a button inside a target application — even when that window is **minimized, hidden, or running in the background**.

Unlike a traditional auto-clicker that spams a fixed screen coordinate, this tool visually locates the button with OpenCV template matching and sends the click directly to the window via the Win32 messaging API. Your real mouse cursor is never moved, so you can keep working while it runs.

---

## Features

- **Vision-based targeting** — finds the button by image, not by fixed coordinates, so it still works if the button moves.
- **True background clicking** — clicks windows that are minimized or behind other windows using `PostMessage`, without stealing your mouse or focus.
- **Hardware-accelerated capture** — uses `PrintWindow` with `PW_RENDERFULLCONTENT` to capture DWM / Electron / GPU-rendered windows.
- **Global hotkeys** — press **F8** to capture a target and **F9** to start/stop, from anywhere.
- **Adjustable scan interval** — tune the scan/click rate from 0.1s to 5.0s with a slider.
- **Live activity log** — real-time feedback with match confidence and click counts.
- **Persistent profiles** — remembers your target window and interval in `config.json`.
- **Standalone build** — ships as a single `.exe` via PyInstaller.

---

## How It Works

1. **Capture the target (F8)** — hover over the button you want clicked and press F8. The app screenshots a small region around your cursor, saves it as `target_button.png`, and records the parent window's title.
2. **Scan the window** — while running, it silently captures the target window's pixels each cycle, even in the background.
3. **Match** — the capture is converted to grayscale and compared against `target_button.png` using `cv2.matchTemplate` (`TM_CCOEFF_NORMED`). A confidence above **0.80** counts as a match.
4. **Click** — the match position is translated to client coordinates and a virtual `WM_LBUTTONDOWN` / `WM_LBUTTONUP` pair is posted directly to the button's window.

---

## Requirements

- Windows OS (uses the Win32 API)
- Python 3.8+

Python dependencies (see `requirements.txt`):

```
pyautogui
keyboard
opencv-python
pywin32
```

---

## Installation & Usage

### Option 1 — Run from source

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the app
python autoclicker.py
```

Or simply double-click **`run.bat`**, which installs the requirements and launches the app.

### Option 2 — Run the prebuilt executable

Run `dist/autoclicker.exe` directly. No Python installation needed.

### Using the app

1. Launch the app. The window stays on top.
2. Hover your mouse over the button you want to click and press **F8** to capture it. The status changes to *Target Set*.
3. Adjust the **Scan/Click Interval** slider if needed.
4. Press **F9** (or click **START ENGINE**) to begin. Press again to stop.

---

## Building the Executable

The project uses PyInstaller with the included spec file:

```bash
pip install pyinstaller
pyinstaller autoclicker.spec
```

The build outputs to `build/` (intermediate) and `dist/autoclicker.exe` (final).

---

## Project Structure

```
auto click/
├── autoclicker.py      # Main application (Tkinter UI + vision engine)
├── autoclicker.spec    # PyInstaller build configuration
├── requirements.txt    # Python dependencies
├── run.bat             # One-click install + run script
├── config.json         # Saved target window title + interval (auto-generated)
├── target_button.png   # Captured button image (auto-generated)
├── build/              # PyInstaller intermediate files (generated)
└── dist/               # Final executable output (generated)
```

---

## Hotkeys

| Key | Action                     |
|-----|----------------------------|
| F8  | Capture target under mouse |
| F9  | Start / stop the engine    |

---

## Notes & Limitations

- **Windows only.** The background-clicking mechanism relies on the Win32 API (`pywin32`).
- Some applications ignore posted messages or block `PrintWindow`; results can vary per app.
- The match threshold is fixed at `0.80` in code — lower it for looser matching, raise it for stricter matching.

---

## Disclaimer

This tool is intended for automating repetitive tasks in software you own or are authorized to use. Do not use it to violate the terms of service of any application or platform. Use responsibly.
