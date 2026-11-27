# Aura UI — Unified Ambient Computing & State-Aware Search

**Course:** Human-Computer Interaction (HCI)  
**Institution:** Institute of Business Administration (IBA)  
**Team Members:** Sharique Baig · Maira Aijaz · Barkhi Khan

Aura UI is a privacy-preserving desktop ambient computing assistant and state-aware search system. Instead of forcing modal interruptions during deep work or tailoring answers solely to a prompt, Aura infers cognitive strain continuously from peripheral behavioral telemetry and adapts both sensory comfort and generated search layouts while preserving user agency.

> **Architecture Note:** The repository root now runs the redesigned unified **Aura UI** (headless Python daemon + system tray + single-instance React/PyWebView shell). The previous v1 Tkinter baseline is preserved intact in `old_version/`.

---

## Key Capabilities

### 1. Unified Calm-Technology Shell (`run.py`, `backend/daemon_controller.py`)
- **Headless Ambient Daemon + Peripheral Tray Ring:** Samples telemetry at 3 Hz without taking over screen space, updating a calm/mild/elevated ring in the system tray.
- **Single-Instance Window (`backend/search/window.py`):** Launching from the tray menu or pressing **`Ctrl+Shift+Space`** focuses the unified React/PyWebView shell (`Search`, `Wellness`, `Setup & Calibration`, and `Lab Console`).
- **Silent Focus Mode & Digest:** Holds system notifications silently during Elevated load (`tier == 2`) without firing red popups, then surfaces one calm **`FocusDigestBanner`** after recovery.
- **Tiered Mixed-Initiative Escalation:**
  - *Tier 1 (0–15 s Elevated):* Silent peripheral comfort adaptation only (optional screen brightness/warmth easing, audio easing).
  - *Tier 2 (≥ 15 s sustained Elevated, or ≥ 4 s in Demo/Sim):* Non-focus-stealing corner **`AmbientNudgePill`** offering a **20s sigh**, **Check in**, or **Snooze 30m**.

### 2. DPI-Normalized Sensing & Interactive Calibration
- **Privacy-First Telemetry (`backend/telemetry_daemon.py`):** Tracks flight-time variability (CoV), backspace error rate, dwell time, and screen-diagonal-normalized mouse agility (`StressEngine` in `backend/stress_engine.py`). Typed characters, key codes, passwords, and window titles are never stored.
- **Typing-Game 30 s Rhythm Calibration (`OnboardingWizard.tsx`):** Monkeytype-style upper passage mirrors keystrokes live with WPM, accuracy, key-error shake feedback, rhythm pulse indicator, and optional synthesized soft keystroke sounds, saving personal `baseline_cov`, `baseline_err`, `baseline_kps`, and `baseline_dwell` baselines used by `state_fusion.py` and `xai.py`.

### 3. State-Aware Generative-UI Search (`backend/search/`, `search_ui/`)
- **Progressive SSE Streaming (`POST /api/search/stream`):** Streams real-time pipeline stages (`Searching sources…` → `Extracting cited facts…` → immediate Stage A TL;DR preview → `Tailoring layout…`) with a live 3-step pipeline tracker, mood-matched shimmer wireframes, `AbortController` **Cancel**, and **Recent Searches** (`/` shortcut focuses search).
- **Facts First, Then Form:** Stage A synthesizes cited claims (via OpenRouter with failover, or extractive fallback offline) over web results (Tavily / Wikipedia / fixed `search_fixtures/`). Stage B composes widgets constrained to the active policy, validating grounded claims and removing unsupported phrases.
- **Inline Citation Hover Previews:** Citation badges (`≥ 24×24 px`) show domain, title, snippet, external link, and jump-to-source preview on hover or keyboard focus.
- **Non-Diagnostic Presentation Modes (`ViewModeMenu.tsx`):** Users can leave **Auto-adapt** on or switch anytime between **Standard View** (`neutral`), **Focused View** (`focused`), **Simple View** (`overwhelmed`), **Easy-Read View** (`fatigued`), **Guided View** (`disoriented`), and **Explore View** (`energized`), with secondary chrome softly receding in Simple and Easy-Read views.
- **Quick Mood Simulator:** Toggle the **Moods** bar in the header (or Lab → Sim & Demo) to preview how each mood adapts the workspace atmosphere, typography, and search layout.

### 4. Themes, Ambient Soundscapes & Wellness (`WellnessView.tsx`)
- **5 WCAG-Verified Themes × 6 Mood Atmospheres (`search_ui/src/index.css`):** Choose from **Dark (Calm Obsidian)**, **Slate (Nordic Dusk)**, **Light (Warm Paper)**, **Sepia (Book Parchment)** (all ≥ 4.5:1 AA text contrast and ≥ 3.0:1 interactive borders), or **High Contrast** (≥ 7:1 AAA), plus full `@media (prefers-reduced-motion: reduce)` support.
- **Procedural Ambient Soundscapes (`useAmbientSound.ts`):** Client-side Web Audio synthesizer for **Soft Rain**, **Brown Noise**, and **Calm Drone** with adjustable volume, auto-play in Simple/Easy-Read option, and header mute chip.
- **Unified Breathing, Chat & Journal:** Single SVG **Physiological Sigh** guide (`UnifiedBreathing.tsx`), empathetic **Aura Check-in** (`LLMController`), Windows Core Audio / optional Spotify volume ducking, and an independent **Session Journal** that saves notes without interrupting active study recordings.

### 5. Research Rigor, Blinding & Exports (`backend/research.py`, `LabConsoleDrawer.tsx`)
- **3-Step Setup Wizard:** Explicit dynamic **Consent v4** storage disclosure, 30 s rhythm calibration, and opt-in comfort/theme settings.
- **Participant Blinded Mode:** Starting a study recording automatically locks the **Lab Console** (`blinded = true`), hiding condition toggles (`Active B` vs. `Control A`), diagnostic state labels, and model/timing debug footers until unlocked by a facilitator (`Ctrl+Shift+L`).
- **Explicit Session Wrap-Up (`SessionWrapUpModal.tsx`):** Stopping a recording opens an explicit modal with **Save & Finalize** (with 0–10 Perceived Stress, 0–10 Mood, optional note/reflection), **Skip ratings**, or **Resume recording**—preventing accidental data loss.
- **Two-Step Confirmed Withdrawal:** Deleting local sessions and uploaded Firestore copies requires explicit confirmation inside Wellness → Privacy.
- **1-Click Integrity Audit & Exports:** Lab Console → Study verifies SHA-256 hash chains and exports all 6 de-identified CSVs (`sessions.csv`, `ticks.csv`, `searches.csv`, `search_events.csv`, `tasks.csv`, `surveys.csv`) to an `exports/` folder or as a direct `aura_study_export.zip` download.

---

## Running Main Aura UI vs. Archived v1

Both the root main app and `old_version/` default to port **`8765`** and automatically fall back to the next free port (`8766`, …) if another instance is open, so you can run and compare them side by side:

| Version | Command (from repo root) | Architecture |
|---|---|---|
| **Main (Aura UI)** | `python run.py` | Headless tray daemon + single unified React/PyWebView shell |
| **Main (Lab Open)** | `python run.py --lab` | Launches with Researcher & Developer Lab Console unlocked |
| **Main (Standalone Dev)** | `python -m backend.search.server --standalone --open` | UI + search server with simulated telemetry (no hardware hooks) |
| **Old Version (v1)** | `cd old_version && python run.py` | Original Tkinter dashboard + separate Search window |

> **Note:** Root and `old_version/` keep isolated `settings.json`, `journal.json`, `secrets.json`, and `data/` folders.

---

## Installation & Build

### Prerequisites
- Python 3.9+ (Windows 10/11 64-bit recommended for brightness, color temperature, Core Audio volume, and Focus Assist controls)
- Node.js 18+ & npm (only needed when rebuilding `search_ui/dist`)

### Setup & Run
```bash
pip install -r requirements.txt
# Optional extras:
pip install ".[window]"   # pywebview native window shell
pip install ".[vision]"   # optional local webcam expression sensor
pip install matplotlib    # session chart plotting (plot_session.py)

python run.py
```

### Frontend Development & Rebuild
```bash
cd search_ui
npm install
npm run build   # outputs to search_ui/dist/ served by backend/search/server.py
```
For live UI hot-reload against the standalone backend:
```bash
# Terminal 1 (from repo root)
python -m backend.search.server --standalone --token dev

# Terminal 2
cd search_ui && npm run dev   # open http://localhost:5173/?t=dev
```

### Package Standalone Executable
```bash
cd search_ui && npm run build && cd ..
python build_exe.py   # -> dist/AuraUI.exe
```

### Run Test Suite
```bash
python -m unittest discover -s tests -q
```

---

## Documentation
- **[Tester Notes](docs/TESTER_NOTES.md):** Quick-start participant & tester guide.
- **[Human Testing & Experimental Framework](docs/TESTING_FRAMEWORK.md):** A/B protocol, NASA-TLX / SUS, SHA-256 audit, CSV exports, and analysis playbook.
- **[Aura Search Study Protocol](docs/AURA_SEARCH_STUDY_PROTOCOL.md):** Search-specific 2×2 protocol, ablations, and logged schema.
- **[Lab Setup Guide](docs/LAB_SETUP.md):** Multi-station Windows lab deployment and station scripts (`tools/setup_station.ps1`).
- **[Firebase Setup Guide](docs/FIREBASE_SETUP.md):** Firestore anonymous sync configuration.
- **[Aura Search Architecture Plan](docs/AURA_SEARCH_PLAN.md):** Original research motivation, literature synthesis, and Phase 0–7 design spec.
