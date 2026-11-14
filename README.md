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
- **Keystroke Dynamics**: Computes Coefficient of Variation (CoV) of flight times, dwell times, and error/backspace frequencies over rolling time windows.
- **Mouse Dynamics**: Analyzes mouse trajectory distances and sudden jitter/clicking spikes to detect physical agitation.
- **Baseline Calibration**: Includes a 30-second resting calibration workflow to tailor thresholds to individual typing baselines.
- **Stress Tiers**: Categorizes user state into 3 adaptive tiers:
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
- **OpenRouter Integration**: Powered by OpenRouter chat completions (`nvidia/nemotron-3.5-super-vl:free` or any configured model) using lightweight zero-dependency standard library requests.
- **Proactive Check-Ins**: Gently prompts the user when sustained frustration is detected without being intrusive.
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

In the app: **Privacy** → enter a participant code → **Save consent**, then tick
**Record session**. End a session from **Journal** (set *Perceived stress* / *Mood* and
**Save entry**) so the self-report is attached to the summary.

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
The **Web API key is public by design** — it identifies the project, not a user; the
rules above are what grant access. Each session becomes one document
`aura_sessions/{pseudonym}_{session_id}` holding the summary plus a `tick_data` array of
numeric per-tick rows. Offline or failed uploads stay queued locally and retry every
5 minutes; nothing is deleted until a push succeeds. The salt, participant code, journal
and any keystroke content are never uploaded; the journal note and its reflection are,
under the same pseudonym. Free tier: 20K writes/day (one write per session) and 50K
reads/day.

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

**The one exception - Aura chat.** An OpenRouter key is a real secret billed to whoever owns
it, so it is *never* compiled in. Without one the app runs normally and the chat panel says
it needs a key. To enable it, put a `secrets.json` beside the exe:

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
1. Enable **Record session** in the Aura UI or run a test.
2. Run the visualizer:
```bash
python plot_session.py
```
This produces high-resolution session charts (`aura_session_chart.png`) illustrating stress dynamics, interventions, and recovery curves.
