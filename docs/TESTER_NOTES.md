# Aura UI — Tester notes

Two minutes of setup, then just work normally. No installation, no Python, no config files needed when running the packaged exe.

---

## 1. Run it

1. Download `AuraUI.exe` anywhere writable (Desktop, Documents — **not** `C:\Program Files`,
   which is read-only and prevents saving sessions), or run `python run.py` from the repository root.
2. Double-click `AuraUI.exe` (first launch takes a few seconds while it unpacks). Aura opens a
   unified window with **Search** and **Wellness** tabs and places a status ring in the system tray.
   Pressing **`Ctrl+Shift+Space`** brings the window back into focus anytime.

> **"Windows protected your PC" (SmartScreen).**
> Expected because the binary is not code-signed. Click **More info → Run anyway**.

Windows 10/11, 64-bit.

## 2. Complete setup & consent (nothing is recorded without consent)

On first launch, the 3-step **Setup & Calibration** wizard opens automatically (you can reopen it
anytime via the **sliders icon** in the top-right header):

1. **Step 1 — Privacy & Data Consent (Consent v4):** Enter the **participant code** your researcher
   gave you, decide whether search query text may be stored (or hashed only), read the consent
   summary, and click **I Consent · Continue**.
2. **Step 2 — 30-Second Rhythm Calibration:** Click **Start 30s Calibration** and type the prompt
   passage at your natural pace. Errors and typing cadence highlight live (with optional soft key
   sounds) and save your personal typing baseline.
3. **Step 3 — Ambient Comfort Preferences:** Opt in to Screen Comfort, Focus Mode, Audio Easing, and
   choose your preferred color theme (**Dark**, **Slate**, **Light**, **Sepia**, or **High Contrast**).

## 3. Record a study session

1. Open the **Researcher Lab Console** by clicking **Lab** in the header (or pressing **`Ctrl+Shift+L`**).
2. In the **Study** tab, confirm your assigned condition (**Active (B) — State-aware** or
   **Control (A) — Prompt-only**), if your facilitator asked you to check it.
3. Click **Start Recording**. Recording starts immediately and locks the Lab Console into
   **Participant Blinded Mode** so study labels and diagnostics stay hidden while you work.
4. Work and search normally. If a **Study** task panel appears in Search, click **Start** on a task,
   click **I'm done** when finished, and submit the short post-task / SUS ratings.
5. When the recording block ends, press **`Ctrl+Shift+L`** to open **Lab → Study** and click **Stop
   Recording**. The **Finish Recorded Session** modal opens automatically:
   - Set **Perceived stress (0–10)** and **Overall mood (0–10)**, optionally add a reflection note,
     and click **Save & Finalize** (or **Skip ratings** / **Resume recording** if stopped by mistake).
6. In **Lab → Study**, you can verify **SHA-256 Verified ✓**, export CSVs to a folder, or download
   `aura_study_export.zip`. Cloud Sync status also shows queued/uploaded status in **Lab → Study**.

## 4. Wellness, Theme & Soundscapes

Open the **Wellness** tab anytime to:
- Switch themes (**Dark**, **Slate**, **Light**, **Sepia**, **High Contrast**) or toggle Ambient Comfort.
- Play built-in **Ambient Soundscapes** (**Soft Rain**, **Brown Noise**, **Calm Drone**), adjust
  volume, or enable auto-play in calmer layout modes.
- Link **Spotify** (optional; playback controls require an active Spotify device, and dev-mode apps
  are limited to allowlisted testers—otherwise Aura eases **Windows system volume** automatically).
- Open the **Physiological Sigh** breathing guide, chat with **Aura Check-in**, or write in **Session
  Journal** (saving a journal note never stops an active recording).

## 5. What is and isn't recorded

- **Recorded (only while recording):** typing speed, timing variability, backspace rate, dwell time,
  mouse movement, score/tier over time, search queries (or salted hashes if chosen) and layouts
  shown, self-report ratings, and any journal note you explicitly save.
- **Never recorded:** typed characters outside Search, passwords, key codes, window titles, app
  names, or webcam video frames.
- **Privacy → Manage data → Withdraw & delete data…** requires explicit confirmation and removes
  your local session files *and* the Firebase documents this install uploaded.

## Where it keeps your data

Everything lives beside `AuraUI.exe` (or `run.py`) in `data/`, `exports/`, `settings.json`, and
`journal.json` (or `%APPDATA%\AuraUI` if the exe folder is read-only).
