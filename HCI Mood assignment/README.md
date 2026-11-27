# AURA — Emotional AI Agent & Empirical HCI Research Workbench

**AURA** is a local-first, privacy-preserving **Emotional AI Agent + Generative UI + Empirical HCI Research Suite**.

Traditional Generative UI systems are **prompt-only**: two users typing the exact same prompt receive the identical layout and response regardless of stress, fatigue, or cognitive load. AURA bridges that gap by conditioning **Visual Type**, **Nav Type**, decision density, interaction hit-targets, and agent reasoning on live facial affect (`OpenCV YuNet` + `HSEmotion ONNX`), while logging full **ISO 9241-11** usability metrics (`Efficiency`, `Effectiveness`, `Satisfaction (SUS)`), **SAM** ground-truth affect, and **NASA-TLX** workload into SQLite/CSV for controlled A/B HCI studies.

---

## 1. Computer Vision Pipeline (`OpenCV YuNet` + `HSEmotion ONNX`)

1. **Stage 1 — `OpenCV FaceDetectorYN` (YuNet `face_detection_yunet_2023mar.onnx`)**:
   - Detects faces + **5 facial landmarks** (eyes, nose, mouth corners) locally in RAM.
   - Computes geometric behavioral cues: **head roll angle**, **horizontal yaw asymmetry**, and **vertical pitch droop** to derive an `attention_score`.
2. **Stage 2 — `HSEmotion EfficientNet-B0` (`enet_b0_8_best_vgaf.onnx`)**:
   - Classifies **8 AffectNet emotions** (`anger`, `contempt`, `disgust`, `fear`, `happiness`, `neutral`, `sadness`, `surprise`) mapped onto **Russell's Circumplex (`Valence × Arousal`)** + a **Cognitive Load Index (`0.0–1.0`)**.
   - **Temporal Anti-Thrashing**: EMA smoothing (`α = 0.28`), configurable dwell timer (`3.0s` default), cooldown (`5.0s`), and a tracked `flickers_prevented` metric.

> **Privacy-First Hardware Shutter**: Video stays strictly in local RAM. Clicking **Cam Off** releases `VideoCapture` immediately.

---

## 2. Emotional AI Agent: Same Prompt, Divergent Visual & Nav Types

Available across both **Commerce Agent** (12-item catalog inspired by Daraz/PriceOye comparisons) and **Study Workspace**, with **Hybrid Offline + Optional Gemini/OpenAI API** support:

| Condition / Emotion | Visual Type | Nav Type | Structural & Agent Adaptation |
| :--- | :--- | :--- | :--- |
| **Control (Prompt-Only)** | `Standard Z-Pattern Grid (Control)` | `Horizontal Top-Down (Control)` | Ignores emotion; renders all 12 items + promos + static horizontal nav. |
| **Focused** | `Focused & Spotlight` | `Bento Box` | Top Spotlight match + Bento Box comparison cards & spec matrix. |
| **Overwhelmed** | `Focused & Spotlight` | `Single-Path Guided Stepper` | **Hick's Law** collapse to **1 card**, 3-step Guided Stepper, **1.26x Fitts targets**, Somatic 4-7-8 pacer (Workspace). |
| **Fatigued** | `Minimalist Calm List` | `Low-Friction Linear Stack` | Filters to top 3 calm options, **1.14x typography (`1.82` line-height)**, **Voice Read-Aloud (`SpeechSynthesis`)**. |
| **Energized** | `Visual Bento & Card Grid` | `Bento Box + Visual Facets` | Multi-card Bento grid, visual category/vendor facets, live side-by-side comparison tray / Kanban. |
| **Disoriented** | `Guided Z-Pattern & Anchor` | `Horizontal Top-Down + Breadcrumbs` | Locks active criteria breadcrumbs / "Where You Left Off" Context Anchor; caps to top 3 choices. |

Use **"Compare Same Prompt Across Emotions"** in the Commerce Agent tab to inspect side-by-side divergence for any prompt.

---

## 3. Empirical HCI Data Logging & Evaluation (`HCI Lab & Data`)

Designed to directly populate and validate an **ISO 9241-11 Evaluation Matrix**:
`Participant / Condition | Emotion Type | Visual Type | Nav Type | Efficiency | Effectiveness | Satisfaction (SUS) | ΔValence`

- **SQLite Persistence (`backend/data/hci_study.db`)**:
  - `sessions`: Timed trial records, ISO 9241-11 `efficiency_score`, `effectiveness_score`, 10-item `satisfaction_sus` (`0–100`), `sam_valence/arousal/dominance` (`1–9`), `cv_sam_alignment (%)`, `nasa_tlx_mental/frustration/effort`, `delta_valence`.
  - `affective_samples`: **1 Hz** continuous CV telemetry (`emotions_json`, `valence`, `arousal`, `attention_score`, `cognitive_load`, `visual_type`, `nav_type`).
  - `interaction_events`: Passive behavioral friction cues (`rage_click`, `hesitation_click`, `backtrack`, `filter_change`, `task_complete`).
  - `agent_generations`: Full log of every prompt, condition, detected emotion, and generated UI schema.
- **1-Click CSV & JSON Export**: Export `sessions`, `samples`, `events`, or `generations` directly for SPSS, R, or Python analysis.

---

## 4. Running Locally

```bash
# 1. Install Python dependencies (if not already installed)
pip install -r requirements.txt

# 2. Launch FastAPI + pre-built React frontend on http://127.0.0.1:8000
python run.py
```

### Run Automated Verification Suite
```bash
python tests/test_pipeline.py
```
