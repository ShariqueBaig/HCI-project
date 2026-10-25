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
  "spotify_client_secret": "YOUR_SPOTIFY_CLIENT_SECRET",
  "spotify_redirect_uri": "http://localhost:8080",
  "openrouter_api_key": "YOUR_OPENROUTER_API_KEY"
}
```

### Spotify Setup (Optional)
1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and log in.
2. Click **Create app**.
3. Set **Redirect URI** to: `http://localhost:8080`
4. Copy the **Client ID** and **Client Secret** into `secrets.json`.
5. Under App Settings > **User Management**, add your Spotify email as a test user.

### OpenRouter Setup (Optional)
1. Sign up at [OpenRouter.ai](https://openrouter.ai/).
2. Generate an API key and paste it as `openrouter_api_key` (or export as `OPENROUTER_API_KEY` environment variable).

*(Note: `secrets.json` and session histories are git-ignored to protect your credentials and privacy.)*

---

## 📦 Building Standalone Executable (.exe)

You can compile Aura UI into a standalone Windows executable using PyInstaller:

```bash
python -m PyInstaller --onefile --noconsole --name "AuraUI" run.py
```

Once the build finishes:
- The compiled standalone executable will be located in `dist/AuraUI.exe`.
- End users can run this single binary without installing Python or third-party dependencies.

---

## 📊 Session Visualization & Evaluation

To generate session charts from recorded telemetry sessions:
1. Enable **Record session** in the Aura UI or run a test.
2. Run the visualizer:
```bash
python plot_session.py
```
This produces high-resolution session charts (`aura_session_chart.png`) illustrating stress dynamics, interventions, and recovery curves.
