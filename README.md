# Aura UI — Intelligent Ambient Stress Intervention System
Human-Computer Interaction (HCI) Course Project

A lightweight, privacy-preserving desktop ambient computing system that continuously infers cognitive load and user stress from peripheral behavioral micro-telemetry (keystroke dynamics and mouse jitter), and responds adaptively through ambient interventions, calm notifications, guided physiological regulation, and empathetic LLM-assisted reflection.

---

## 👥 Team Members
- **Sharique Baig**
- **Maira Aijaz**
- **Barkhi Khan**

---

## ✨ Features & Architecture

### 1. Non-Invasive Stress & Telemetry Engine
- **Keystroke Dynamics**: Computes Coefficient of Variation (CoV) of flight times, dwell times (via stable virtual-key tracking without reading character text), and error/backspace frequencies over a smooth 5-second rolling window.
- **Mouse Dynamics**: Analyzes mouse trajectory distances and sudden jitter/clicking spikes to detect physical agitation.
- **Interactive Baseline Calibration Modal**: Includes a 30-second resting calibration dialog with a sample prose passage, auto-focused typing box, and live progress/sample counter to tailor thresholds to individual typing baselines.
- **Study Condition Toggle (`Mode: Active (B)` / `Mode: Control (A)`)**: Built-in one-click experimental mode switch for within-subjects A/B testing (`Control` logs telemetry silently while suppressing all display, notification, audio, breathing, and chat interventions).
- **Stress Tiers & Hysteresis**: Categorizes user state into 3 adaptive tiers with boundary hysteresis (exit Mild $< 26$, exit Elevated $< 52$) and fast proportional + linear idle release (~2.0s recovery):
  - **Calm** (Score 0–29)
  - **Mild** (Score 30–59)
  - **Elevated** (Score 60–100)

### 2. Ambient Sensory Interventions
- **Adaptive Screen Brightness**: Gradually eases monitor backlight down during stress spikes to reduce sensory overstimulation.
- **Adaptive Color Temperature**: Smoothly adjusts display gamma temperature (down to warm ~3500K) using native Windows GDI ramps to promote cognitive relaxation.
- **Spotify Auto-Volume**: Automatically lowers playback volume when stress elevates and restores it as the user calms down.

### 3. Focus Mode & Calming Notification Queue
- **Intelligent Notification Gatekeeper**: Automatically holds back non-urgent system alerts when stress reaches the *Elevated* tier (or native Windows Focus Assist DND).
- **Post-Stress Digest**: Bundles and delivers a gentle summary toast of all held notifications once the user returns to *Calm*.

### 4. Physiological Sighing & In-App Breathwork
- **Interactive Breathing Guide**: An animated, science-backed physiological sighing popup (double inhale + extended exhale) triggered on prolonged elevated stress or on-demand.

### 5. Empathetic LLM Co-Regulation & Reflection ("Aura Chat")
- **Multi-Model OpenRouter Integration + Built-In Local Coach**: Powered by OpenRouter chat completions with automatic failover across multiple free models (`nvidia/nemotron-3-super-120b-a12b:free`, `meta-llama/llama-3.3-70b-instruct:free`, `google/gemma-3-27b-it:free`, `openrouter/free`) and a context-aware built-in empathetic coach fallback so check-ins and chat work 100% of the time even offline or without `secrets.json`.
- **Proactive Check-Ins**: Gently prompts the user after 8 seconds of sustained Elevated stress (or 3 seconds in Demo / Simulate Stress mode) without being intrusive.
- **Session Journal & Metacognitive Mirror**: Aggregates session telemetry (durations, peak stress timestamps, intervention counts) and generates personalized reflections and takeaways. Keystrokes are **never** recorded or transmitted—only anonymous aggregate metrics.

### 6. Interactive Demo & Session Analysis
- **Scripted Presentation Demo**: Built-in 4-stage automated presentation mode and manual stress level overrides to showcase real-time adaptive transitions without needing manual stress induction.
- **Telemetry Logger & Plotting**: Session recording into CSV and plotting tool (`plot_session.py`) for generating publication/poster quality session charts.

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.9+ (Windows recommended for native display brightness, color temperature, and notification controls)

### 2. Installation
Clone the repository and install required dependencies:
```bash
pip install -r requirements.txt
```

*(Optional for session visualization charts)*:
```bash
pip install matplotlib
```

### 3. Running in Development
```bash
python run.py
```
*Note: Any changes to the code can be tested instantly by closing the app and re-running this command.*

### 4. Install as a package

Aura UI is a standard Python package (`pyproject.toml`), so it can be installed and run
as a command instead of a checkout:

```bash
pip install .            # or: pip install -e . for development
aura-ui                  # launches the desktop widget
```

Optional extras:

```bash
pip install ".[plots]"   # matplotlib -- session charts + the Phase 2 experiment scripts
pip install ".[build]"   # pyinstaller -- the standalone AuraUI.exe below
```

**Where your files live:** `secrets.json`, `settings.json`, `journal.json`, `.cache` and
the `data/` research store sit next to `run.py` in a checkout, and next to `AuraUI.exe`
in a frozen build. Set `AURA_DATA_DIR` to override; a pip-installed copy defaults to
`%APPDATA%\AuraUI` rather than writing into site-packages.

---

## 🔑 Secrets & API Configuration

To enable Spotify auto-lowering and the Aura LLM chat assistant, configure your API keys:

1. Copy [`secrets.example.json`](file:///d:/OneDrive%20-%20Institute%20of%20Business%20Administration/Sharique/sem7/HCI/HCI%20project/secrets.example.json) to `secrets.json`:
   ```bash
   cp secrets.example.json secrets.json
   ```
2. Open `secrets.json` and provide your credentials:

```json
{
  "spotify_client_id": "YOUR_SPOTIFY_CLIENT_ID",
  "spotify_redirect_uri": "http://127.0.0.1:8080",
  "openrouter_api_key": "YOUR_OPENROUTER_API_KEY"
}
```

### Spotify Setup (Optional)
Aura UI uses **Authorization Code with PKCE**, so there is **no client secret**. Each
user clicks **Connect Spotify** and signs into *their own* account; nothing happens at
launch, and no browser opens until that button is pressed.

1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and log in.
2. Click **Create app**.
3. Set **Redirect URI** to: `http://127.0.0.1:8080` — exactly this. Spotify now rejects
   `localhost`, and HTTP is only allowed for loopback IPs.
4. Copy only the **Client ID** into `secrets.json` (the secret is not used or needed).
5. Development Mode limits: the app owner needs **Spotify Premium**, and up to **5 users**
   must each be added under *Settings → Users Management*, otherwise their API calls
   return HTTP 403. Beyond 5 users you need **Extended Quota Mode** (Spotify review).

### OpenRouter Setup (Optional)
1. Sign up at [OpenRouter.ai](https://openrouter.ai/).
2. Generate an API key and paste it as `openrouter_api_key` (or export as `OPENROUTER_API_KEY` environment variable).

*(Note: `secrets.json` and session histories are git-ignored to protect your credentials and privacy.)*

---

## 🔐 Research Data Collection (privacy-first)

Session recording is consent-gated and pseudonymous, and every record is chained with a
SHA-256 hash so tampering is detectable. Nothing is uploaded; there is no network code
in the collector.

- **What is stored:** numeric typing/mouse aggregates (`keys_per_second`, `error_rate`,
  `mean_dwell`, `std_dwell`, `mean_flight`, `std_flight`, `flight_count`,
  `mouse_distance`, `mouse_clicks`), the stress score/tier, and timings.
- **What is never stored:** characters typed, key codes, window titles, or app names.
  A strict whitelist drops anything else before it reaches disk.
- **Journal note + reflection:** the note you write when saving a session, and the
  reflection Aura generates from it, are stored with that session and uploaded with it
  (consent v3). They are free text — don't write anything you wouldn't want in the
  dataset.
- **Identifiers:** your participant code is stored only as a salted SHA-256 digest; the
  per-install salt (`data/.salt`) is never exported.
- **Retention:** `research.purge_expired(180)`; withdrawing consent deletes all sessions.

In the app: **Privacy** → enter a participant code → **Save consent**, optionally run the
30-second **Calibrate** modal, pick **Mode: Active (B)** or **Mode: Control (A)**, and tick
**Record session** (`● Rec MM:SS` live timer). When you uncheck **Record session** to stop,
the **Journal** opens automatically so you can set *Perceived stress (0–10)* and *Mood (0–10)*
and click **Save entry** to finalize the session with your self-report attached.

For the full human-subjects study protocol, counterbalancing matrix, and analysis guide,
see **[TESTING_FRAMEWORK.md](TESTING_FRAMEWORK.md)**.

### Cloud sync to Firebase (optional, off by default)

Sessions are recorded locally first. If `firebase_config.json` is present, the app also
uploads them — **each install signs in anonymously, so every copy of the app gets its
own identity with no user interaction.** End users never configure anything; you ship
the config file with the app.

**One-time setup (developer):**

1. Firebase console → **Add project** (Spark/free plan) → **Firestore** → *Create database*.
2. **Authentication** → *Sign-in method* → enable **Anonymous**.
3. **Project settings → General** → copy **Project ID** and the **Web API key**.
4. Copy `firebase_config.example.json` → `firebase_config.json` and fill in both values.
5. Firestore → **Rules** → paste (this is what makes uploads safe):

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /aura_sessions/{doc} {
      allow create: if request.auth != null
                    && request.resource.data.uid == request.auth.uid;
      allow delete: if request.auth != null
                    && resource.data.uid == request.auth.uid;
      allow read, update: if false;
    }
  }
}
```

Full walkthrough with a troubleshooting table: **[FIREBASE_SETUP.md](FIREBASE_SETUP.md)**.
For the complete illustrated application, setup, and testing guide (with UI screenshots), see **[AURA_UI_GUIDE.tex](AURA_UI_GUIDE.tex)**.
The **Web API key is public by design** — it identifies the project, not a user; the
rules above are what grant access. Each session becomes one document
`aura_sessions/{pseudonym}_{session_id}` holding the summary plus a `tick_data` array of
numeric per-tick rows (automatically downsampled to at most 800 evenly spaced points while
preserving the start, peak-stress, and end ticks so long sessions stay safely below Firestore's
1 MiB document limit; full 3 Hz data stays in the local `.jsonl` file). Offline or failed
uploads stay queued locally and retry every 5 minutes; nothing is deleted until a push
succeeds. The salt, participant code, journal and any keystroke content are never uploaded;
the journal note and its reflection are, under the same pseudonym. Free tier: 20K writes/day
(one write per session) and 50K reads/day.

The app shows this live in the **Cloud sync** row of the main window: queued count, and
the last upload error when something fails. Withdrawing consent erases the participant's
uploaded documents as well as the local files.

To reproduce the Phase 2 instrument validation (see `Phase_2_Submission/experiment_report.md`):
```bash
pip install matplotlib
python experiments/run_experiment.py
```

## 📦 Building Standalone Executable (.exe)

Aura UI compiles into a single self-contained **AuraUI.exe** - download, double-click, done.
No Python, no config files to place, nothing to edit.

```bash
python -m PyInstaller --onefile --noconsole --name "AuraUI" --add-data "aura_defaults.json;." run.py
```

Once the build finishes:
- The compiled executable is `dist/AuraUI.exe` (~34 MB). **Ship that one file and nothing else.**
- End users run this single binary without installing Python or third-party dependencies.

**Why it needs no setup:** `aura_defaults.json` is compiled into the binary and holds only
*public* app identifiers - the Firebase project id + Web API key (access is governed by the
Firestore rules, not by the key) and the Spotify Client ID (PKCE needs no client secret). At
first launch it signs in to Firebase anonymously, so every copy gets its own identity and
starts syncing with nothing to configure.

**Aura chat in standalone builds:** An OpenRouter key is a real secret billed to whoever owns
it, so it is *never* compiled in. Without `secrets.json`, Aura Chat automatically uses its
built-in context-aware empathetic coach so proactive check-ins and reflection still work out
of the box for every tester. To upgrade a standalone copy to cloud LLM responses, place a
`secrets.json` beside the exe:

```json
{ "openrouter_api_key": "sk-or-..." }
```

Settings, journal, `.cache` and the `data/` research store are created beside the exe (or in
`%APPDATA%\AuraUI` if that folder is read-only).

---

**Handing the exe to testers?** Give them [TESTER_NOTES.md](TESTER_NOTES.md) — SmartScreen,
consent, recording and Spotify steps in one page.

---

## 📊 Session Visualization & Evaluation

To generate session charts from recorded telemetry sessions:
1. Give consent under **Privacy**, select your study mode (**Mode: Active (B)** or **Mode: Control (A)**), enable **Record session**, and stop recording via the **Journal**.
2. Run the visualizer:
```bash
python plot_session.py [path/to/session.jsonl | ticks.csv | session_log_xxx.csv]
```
With no file argument, `plot_session.py` automatically loads the newest non-empty research `.jsonl` session in `data/sessions/` (or legacy `session_log_*.csv`) and produces high-resolution charts (`aura_session_chart_real.png` and `aura_session_chart_poster.png`) illustrating stress dynamics, interventions, and recovery curves.
