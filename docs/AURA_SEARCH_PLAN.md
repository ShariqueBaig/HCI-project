# Aura Search — state-aware generative-UI search (plan)

## Context

There are two prototypes in this repository:

- **Aura UI** (repo root, Tkinter desktop app). It infers stress from keystroke and mouse dynamics and responds with ambient interventions and an OpenRouter chat.
- **HCI Mood assignment** (FastAPI + React web app, currently untracked in git). It infers 5 affective states from the webcam and switches between preset "generative" layouts for a 12-item product catalog.

The goal is **Aura Search**: a search feature **built into Aura UI**. Its answers and interface are generated from the query *plus* the user's live state. Today's generative UI and AI search systems tailor only to the prompt.

**Aura UI stays the product and the host process.** The webcam app is treated as a parts bin:
- the GenUI renderer patterns;
- the 5-state affect model (an optional camera sensor);
- copilot proposals, the XAI drawer, and the SUS, SAM and NASA-TLX instruments.

Those parts are ported *into* Aura. The `HCI Mood assignment/` folder itself is left untouched as its own submission.

Decisions already made:
- Search over the **live web via an API**.
- **Hybrid GenUI**: a constrained component spec, plus one sandboxed custom-HTML slot.
- **OpenRouter with failover** as the single LLM path.

---

## 1. Requirement validation

**Claim.** Current generative search computes `answer = f(query)`, and at best `f(query, stored profile)`. Aura Search computes:

`answer = f(query, live user state, task context, interaction history)`

It applies that to three things:
1. the **content** (depth, length, tone);
2. the **interface** (layout, widgets, number of options);
3. **what happens next** (it acts before the user re-prompts).

### Literature check

I searched arXiv and OpenAlex in Nov 2026. The WebSearch tool was failing, so I queried those two sources directly. Items marked "preprint" are not peer reviewed.

| Strand | Representative work | What it tailors to | Gap left open |
|---|---|---|---|
| GenUI from prompts | Chen et al., *Generative Interfaces for Language Models* (arXiv 2508.19227; Findings ACL 2026). Leviathan et al., *Generative UI: LLMs are Effective UI Generators* (arXiv 2604.09577, preprint). | The query only | Same query gives the same UI for everyone |
| GenUI personalization | Peng, Bigham & Wu, *Efficient Personalization of GenUIs* (arXiv 2604.09876). Kim et al., *Elicitive User Interfaces* (arXiv 2609.23642). | Explicit pairwise feedback or explicit elicitation widgets | Stable preferences only; no moment-to-moment state. Peng: users disagree strongly (α = 0.25), so one-size-fits-all fails. |
| GenUI for agents | *Macaron-A2UI* (arXiv 2605.24830). *GenUI-Harness* (arXiv 2610.11123). | Dialogue context and data | Tied to the text only |
| Proactive search | Meng et al., *Conv2Query* (SIGIR 2025). Dewan, *Anticipatory Retrieval* (SIGIR 2026). | Conversation text | Anticipates *what* to retrieve, not *how* to present it for this user's state |
| Implicit-signal LLM personalization | *GazeSummary* (WMCSA 2026) | Gaze | Closest prior work, but output is text only, with no UI and no search |
| Affect in IR | Arapakis et al. 2008 (SIGIR). González-Ibáñez & Shah 2016 (ASIS&T). Luo et al. 2024, struggle detection via reversal theory. | Affect used as *relevance feedback* or a struggle label | Affect is never used to *generate* the answer or its presentation |
| Why it matters | Crescenzi, Kelly & Azzopardi 2015 (SIGIR) | – | Under time pressure, searchers query faster, view fewer documents and read more shallowly. Stressed users need different presentation. |
| Generative search today | Grossman et al. 2026 (SIGIR): AI Overviews appear for 51.5% of queries | – | Same overview for every user state |

**Verdict.** The gap is real and defensible. No surveyed system closes the loop from **implicit, real-time multimodal state** to **both generated answer content and generated interface** in search, with the user keeping control.

### Risks to design around

These become hard requirements:

1. **"Adapt the form, not the facts."** The user's state must never change *what is true*, only how much is shown and how. Enforced by the two-stage pipeline in §4.
2. **Wrong inference becomes paternalism.** Facial-expression-to-emotion mapping is contested (Barrett et al. 2019). Required mitigations:
   - fuse several signals;
   - gate on confidence;
   - re-layout in **copilot** mode by default (propose, then accept or undo);
   - an always-visible "Standard view" escape;
   - a "Why this layout?" explanation.
3. **Latency hurts stressed users** (Crescenzi 2015). Show a skeleton from the state policy immediately and stream results into it. Cache Stage A so a re-layout needs no new search.
4. **Privacy.**
   - The camera stays optional.
   - Typing capture records timing only, inside the search box.
   - Only the submitted query goes to the search API and the LLM.
   - Consent and pseudonymisation come from Aura.

---

## 2. Aura UI vs HCI Mood app: what each is missing

You are **half right**. Aura UI is the more mature *system*. The Mood app has the architecture this feature *needs*. Neither one is enough alone.

| Dimension | Aura UI (desktop) | HCI Mood app (web) |
|---|---|---|
| Engineering maturity | **Strong.** Packaged exe, settings, tray, threads, hash-chained logs, Firebase sync, Phase 2 validation. | **MVP.** Untracked in git, no packaging, several bugs (below). |
| Research ethics | **Strong.** Consent v3, salted pseudonyms, feature whitelist, retention and erasure. | **Missing.** No consent gate or pseudonymisation; the Gemini key goes in the URL query. |
| Sensing | Non-invasive keystroke and mouse sensing with per-user calibration. **But** it produces one scalar stress score and cannot tell *fatigued* from *overwhelmed*. Only flight-time CoV is used; dwell and mouse are uncalibrated. | A richer model: valence, arousal, attention, cognitive load, 5 states, dwell and cooldown, flicker metric. **But** webcam-only, no calibration, contested FER validity, and the engine advances on every read. |
| Adaptation | Ambient only (brightness, gamma, DND, Spotify, breathing, chat). **No UI or content adaptation and no task.** Notifications are simulated. | Layout and density adaptation, Hick's and Fitts' law rationale, mixed-initiative proposals (accept, dismiss, undo), XAI drawer. **But** the "generative" UI is 5 fixed templates, and the LLM only rewrites 4 text strings. |
| Search / LLM | OpenRouter with 4-model failover and an offline coach (robust). Chat only. | Keyword scorer over 12 hardcoded products. Gemini/OpenAI caller. No retrieval. |
| Study instruments | Self-reported stress and mood 0–10, A/B toggle. | SUS, SAM, NASA-TLX, ISO 9241-11 metrics, same-prompt-across-states compare, rage-click and hesitation telemetry. |

**Conclusion: Aura UI hosts and the webcam app donates parts.**
- Aura keeps what it is best at: the product shell, system-wide keystroke and mouse stress with calibration, interventions, consent and research logging, packaging, and the OpenRouter client.
- It gains what it lacks: a generated interface, a multi-dimensional state, and study instruments.
- Tkinter cannot render a generated web UI, so Aura opens a **native web-view window** (pywebview) on a small local server **running inside the Aura process**.
- Because the server runs inside Aura, the search reads Aura's live `StressEngine` state *directly*. No second app and no bridge are needed.

---

## 3. How search lives inside Aura (Phase 0)

```
Aura UI process (python run.py / AuraUI.exe)
├── Tk main thread: StressEngine @3 Hz ──► _refresh() ──► LiveState snapshot (locked)
├── pynput listeners (system-wide typing/mouse)          │
├── interventions (brightness, DND, breathing, Spotify)  │
└── NEW search server thread: uvicorn 127.0.0.1:8765 ◄───┘ reads snapshot
        ├── /api/search … (backend/search/*)
        └── serves search_ui/dist  ──►  pywebview "Aura Search" window
```

1. **Entry points into Aura.**
   - A **Search** button in `_build_controls` (`run.py:559`).
   - A tray menu item in `_setup_tray` (1921).
   - A global hotkey (Ctrl+Shift+Space) via `pynput.keyboard.GlobalHotKeys`.
   - All three open or focus the pywebview window. If pywebview is missing, fall back to `webbrowser.open`.
2. **Server thread.**
   - `_start()` (1491) starts uvicorn in a daemon thread, bound to `127.0.0.1` only. Port 8765, never 8080, which Spotify PKCE uses.
   - `_quit()` (1935) stops it.
   - A random per-launch token is passed to the window URL and required on every request, so other local processes cannot drive it.
3. **`LiveState` snapshot.**
   - Built in `_refresh` (around `run.py:1878`) on the Tk thread, so the stateful `engine.tier` getter is never read from another thread.
   - Stored under a `threading.Lock`.
   - Fields: `score`, `tier`, `label`, the 9 features plus `cov`, `condition`, `calibrated`, `dnd_active`, `focus_blocking`, `breathing_active`, `held_count`, `simulated`, `demo`, `recording`, `session_stats`.
4. **Package layout.**
   - Everything goes inside Aura's existing `backend/` package: `backend/search/` (server and pipeline) and `backend/stress_engine.py`. `StressEngine` moves out of `run.py:104-198` unchanged; `run.py` imports it back.
   - React source goes in `search_ui/` at the repo root; its build output is `search_ui/dist`.
   - Nothing imports from `HCI Mood assignment/`. Useful code is **ported** (copied and adapted), and that folder stays as it is.
5. **`backend/llm_controller.py` gains `complete_json(messages, max_tokens, timeout)`.**
   - It reuses `_load_key`, `MODELS`, `_complete_model` and `_complete`.
   - It adds `response_format: json_object`, tolerant JSON extraction, and moving to the next model on parse failure.
   - `chat()` is unchanged.
6. **Optional camera sensor (`[vision]` extra).**
   - Port `vision_engine.py`, `affective_engine.py` and `model_manager.py` into `backend/vision/`.
   - Off by default, in keeping with Aura's privacy stance.
   - Fix the read-advances-the-engine bug while porting: tick on a fixed timer and read from a cache.
   - The ONNX models download on first enable; they are never bundled into the exe.
7. **Aura's A/B toggle drives the search condition.**
   - Control (A) means prompt-only search.
   - Active (B) means state-aware search.
   - The study switch is one control, as it is today (`_toggle_condition`, `run.py:630`).
8. **Dependencies and packaging.**
   - Add `fastapi`, `uvicorn` and `pywebview` to `pyproject.toml` and `requirements.txt`. Vision extra: `opencv-python` and `onnxruntime`.
   - PyInstaller gets `--add-data "search_ui/dist;search_ui/dist"`.
   - The `secrets.example.json` template gains `tavily_api_key`.
9. **Dev mode.** `python -m backend.search.server --standalone` runs the search UI with a simulated `LiveState` for frontend work.

---

## 4. Core architecture: the two-stage "facts, then form" pipeline

```
query ─► Retrieval ─► STAGE A: grounded synthesis (state-blind, cached)
                         │  canonical claims[] with citation ids, sources[]
user state ─► Fusion ─► Policy ─► STAGE B: state-conditioned GenUI composer
                                     │  spec = selects/condenses claims → widgets
                                     ▼
                         Validator (schema, policy caps, citation ids ⊆ Stage A)
                                     ▼
                         React renderer (+ sandboxed custom slot) ─► interactions
                                     ▲                                   │
                         Anticipation loop ◄── struggle / state change ◄─┘
```

- **Stage A never sees the user's state.** That guarantees truth invariance, and it doubles as the **prompt-only control condition**: Stage B with a neutral policy.
- **Stage B may only *select, order and condense* Stage A claims.** It adds no new facts. The validator rejects any claim or citation ID that is not in Stage A.
- **A state change re-runs only Stage B**, about 1–3 s with no new search. This is what makes the mid-reading re-layout ("one step ahead") practical.

### New backend modules (Aura `backend/search/`)

**`providers.py`**
- `SearchProvider` protocol: `search(query, k) -> list[Source{id, title, url, snippet, content, published}]`.
- `TavilyProvider` (default). It returns LLM-ready content and has a free tier. The key comes from `secrets.json` `tavily_api_key` or the env var `TAVILY_API_KEY`.
- `BraveProvider` (optional).
- `FixtureProvider`. Cached JSON results per study task under `search_fixtures/` at the repo root (tracked in git; not under the git-ignored `data/`), for offline demos and **reproducible studies**: every participant sees the same sources. A "record fixtures" CLI flag captures live results into fixtures.

**`synthesis.py`** (Stage A)
- LLM JSON call that returns `{tldr, claims[{id, text, source_ids, importance 1-3}], key_entities[], comparison_axes[], steps[]?}`. The temperature is low, and the output is cached by `(query, source ids)`.
- Offline fallback: extractive claims from top snippets with no LLM, so it always returns something.

**`state_fusion.py`**: `fuse(live_state, query_typing, affect?, behavior, context) -> UserStateVector`.
- Inputs:
  - **Aura `LiveState`, always available.** It carries:
    - the system-wide calibrated stress score and tier, from what the user did *before* opening search;
    - the features;
    - intervention flags (`breathing_active`, `dnd_active`, `focus_blocking`).
  - **Query-typing stress.** A second, short-lived `StressEngine` instance fed from the search box's own keystroke timing, using the same baseline from Aura's calibration.
  - **Optional camera affect** (`backend/vision/AffectiveEngine`): valence, arousal, cognitive_load, attention, active_state, confidence.
  - **Behavioural friction:** rage clicks, hesitations, backtracks, reformulations, scroll and dwell on results.
  - **Context:** query trail, time on task.
- Intervention coupling:
  - While Aura's breathing guide is open, the search stays `silent`.
  - While Elevated with focus blocking on, the policy leans toward the *overwhelmed* layout.
- Output: `{state ∈ 5 HCI_STATES, confidence, stress_0_100, cognitive_load, valence, arousal, query_uncertainty, struggle, signal_contributions{}, sources_available[]}`.
- Rules:
  - Confidence-weighted. With the camera off (the default), map Aura's 1-D stress plus typing tempo and behaviour onto the 5 states:
    - high stress plus friction → *overwhelmed*;
    - low key rate, long dwell and slow flight with low stress → *fatigued*;
    - reformulation loops or a long time on task with low progress → *disoriented*;
    - fast, steady typing with low error → *focused* or *energized*.
  - The camera, when enabled, settles the cases typing cannot (valence).
  - Port the classifier thresholds from `HCI Mood assignment/backend/affective_engine.py` `_classify_state` (196-219).
  - Port the dwell and hysteresis from `update` (324-363) so the layout does not flicker.

**`policy.py`**: deterministic `State → AdaptationPolicy`. These are the guardrails the LLM must stay inside. Fields:
- `answer_word_budget`
- `reading_level`
- `max_primary_options`
- `allowed_widgets[]` / `required_widgets[]`
- `density`, `tone`
- `show_facets`, `show_sources_inline`
- `proactive{clarifiers, followups, breathing_nudge}`
- `allow_custom_widget`

It is seeded from the webcam app's `VISUAL_NAV_TAXONOMY` (`HCI Mood assignment/backend/emotional_agent.py:231-304`) and `STATE_DESCRIPTIONS` (`generative_ui_engine.py:10-171`), including `targetScale`, `typographyScale`, `lineHeight` and `surfaceTokens`. Those values drive the CSS-variable token system ported from that app's `App.tsx:39-71`.

| State | Policy |
|---|---|
| Overwhelmed | One TL;DR answer and a GuidedSteps widget. At most 1 option. No facets. Larger targets. Optional breathing nudge. |
| Fatigued | A short KeyFacts list and read-aloud, about 80 words, high line height. |
| Energized | ComparisonTable, facets, exploration follow-ups, and the custom widget is allowed. |
| Disoriented | QueryTrail / ContextAnchor breadcrumbs and "where you left off", top 3 options. |
| Focused | AnswerCard, sources inline, and a dense comparison. |

**`composer.py`** (Stage B)
- LLM JSON call. Input: Stage A output, policy and a short state summary.
- Output spec:
  ```
  {topology, components[{type, props, claim_ids, source_ids}],
   followups[], clarifiers[], custom_widget?{title, html}, rationale}
  ```
- Deterministic offline composer: a template per state over the Stage A claims.

**`validator.py`** (Pydantic)
- Rejects unknown component types.
- Enforces policy caps by truncating, not failing.
- Checks that claim and source IDs are in Stage A.
- Strips `custom_widget` when the policy disallows it.
- Size-caps the HTML.

**`context_window.py`**: dual sliding window, borrowed from AURA (Lu et al. 2026), §4b.
- A **dense window** keeps the last N = 30 s of raw affect and typing samples at 1 Hz. It is used only by fusion and the decision loop.
- A **text window** keeps the last M = 10 *query groups*. A group is one query plus its spec summary, the interactions on it, and the state at render time, condensed to about 1 line each.
- Only the text window and the current state summary go to the LLM, so prompt size and latency stay bounded however long the session runs.
- Prompt layout puts the fixed parts first and the changing parts last: system prompt, then Stage A claims, then text window, then current state. That lets provider-side prefix caching (OpenRouter, where available) reuse the start of the prompt across re-layouts.

**`anticipation.py`**: the "one step ahead" loop, run as an **explicit decision policy with silence as the default**.
- At each 1 Hz tick it picks one action: `silent | propose_relayout | offer_clarifier | offer_followup | ack`.
- `silent` must be the overwhelmingly common output. AURA shows that getting this balance wrong breaks proactivity: with an unbalanced loss their model fell silent all the time, scoring 0% on proactive alerting.
- The three AURA response modes, mapped to search:
  - **Reactive.** On submit, render immediately for the current state.
  - **Proactive (deferred).** After render, watch for *enough evidence* (struggle signals sustained past a dwell threshold) before acting once. When the policy is "watching", show a small acknowledgement chip, e.g. "I'll simplify this if it gets heavy". This mirrors AURA's acknowledge-then-answer-later pattern.
  - **Continuous.** On a long reading session with a changing state, allow several Stage B re-layouts without a new query. These are rate-limited by the cooldown and the 18 s dismissal suppression.
- **(a) Pre-submit.** Hesitation, rewrites or backspace bursts while typing the query raise `query_uncertainty`. The response then includes clarifier chips (elicitive), built from Stage A `comparison_axes`.
- **(b) Post-render struggle.** Signals: reformulation (token-Jaccard with the previous query), a quick return after opening a source, stress rising after results, or a long dwell without scrolling. Any of these triggers a **re-layout proposal** ("Simplify to one answer?", "Show a comparison?"). It goes through a search-proposal channel modelled on `AffectiveEngine.respond_to_proposal` (149) with accept, dismiss or undo, and an 18 s dismissal suppression like `dismissed_until`.
- **(c) Next need.** State-tuned follow-up queries. Overwhelmed users get "just tell me what to do"; energized users get "compare X vs Y".

### API (`backend/search/server.py`, a FastAPI app run in Aura's server thread)

Every route requires the per-launch token.

| Method / path | Purpose |
|---|---|
| `GET /api/state` | The fused `UserStateVector` plus Aura's `LiveState`. |
| `WS /ws/state` | Pushes the same at 2 Hz so the state chip and proposals update live. |
| `POST /api/search` | Body `{query, typing_features?}`. The condition is taken from Aura's A/B toggle; it can only be overridden in dev or `--standalone`, to allow C0 classic links. Returns `{search_id, state, policy, stageA, spec, sources, timings{retrieval, stageA, stageB}, used_llm}`. |
| `POST /api/search/{id}/rerender` | Body `{reason, target_state?}`. Runs Stage B only. |
| `POST /api/search/{id}/proposal` | Body `{action}`. |
| `POST /api/search/compare` | The same query across all 5 states plus control; the demo and figures tool. Ported from `compare_prompt_across_emotions` (`emotional_agent.py:638`). |
| `POST /api/telemetry/typing` | Windowed query-box typing features at about 1 Hz. |
| `POST /api/search/event` | Search interactions. |
| `POST /api/search/survey` | Post-task SUS, SAM, NASA-TLX and the 3 Likert items. |

### Research logging: extend Aura's own `backend/research.py`

No second database is added.
- New record types go into the existing consent-gated, hash-chained session `.jsonl`, written by `ResearchCollector`:
  - `search`: query, condition, state vector, policy name, spec summary (component types, claim IDs), source domains, used_llm, model, timings;
  - `search_event`;
  - `search_typing`: whitelisted timing features only;
  - `survey`.
- **Consent goes to v4** (`CONSENT_VERSION`, `CONSENT_TEXT`), because queries are free text. Option: store only a salted hash of the query when the participant declines query logging.
- `export_dataset()` adds `searches.csv`, `search_events.csv` and `surveys.csv`.
- Firebase `build_document` gets only aggregate search counts and timings by default, never the query text, unless consent v4 says otherwise.
- The SUS, ISO 9241-11 and SAM math is ported from `HCI Mood assignment/backend/research_logger.py` (`compute_sus` L18, `compute_iso_metrics` L32, `compute_cv_sam_alignment` L55) into `backend/study_metrics.py`.

---

## 4b. Methodology borrowed from AURA (Lu et al., arXiv 2604.04184, 2026)

**Caveat first.** It is a *different* AURA: a Huawei/CUHK streaming VideoLLM, fine-tuned from Qwen3-VL-8B on 32 accelerators. It watches world-facing video and answers questions. It has no affect modelling, no search and no GenUI, and its model is far beyond what we can train or serve. In the paper, cite it under *proactive / always-on assistants* and name it carefully to avoid confusion with our own "Aura".

**What transfers is its methodology:**

| AURA idea | Our adaptation |
|---|---|
| Treat "stay silent" as an explicit, learned decision, balanced against speaking (Silent-Speech Balanced Loss) | Silent-by-default decision policy in `anticipation.py`. Evaluate it on **both** error types: false interventions (annoyance) and missed interventions (struggle with no help). |
| Taxonomy of Real-Time, Proactive and Multi-Response QA | Taxonomy of Reactive, Proactive-deferred and Continuous adaptation. This gives "one step ahead" a precise, testable definition and becomes a stated contribution. |
| Dual sliding window: short dense video window plus longer text history window | `context_window.py`: N = 30 s of signals, M = 10 query groups, text-only history to the LLM |
| FIFO window with a margin so the KV prefix can be reused | Prompt ordered fixed-to-variable for prefix caching. Stage A is cached so a re-layout runs Stage B only. |
| Coarse-to-fine data engine with an LLM verification stage | Build the **evaluation scenario set** in stages: (1) seed queries across difficulty levels (fact, comparison, multi-step decision), balanced the way AURA balances difficulty; (2) cross each query with the 5 states plus control; (3) record fixtures; (4) **verification**: rule checks (claims ⊆ Stage A, policy caps) plus an LLM-as-judge rubric for grounding and fit to state. |
| Separate RQ on preserving baseline ability (offline benchmarks after streaming training) | **Non-inferiority RQ**: state-aware mode must not reduce accuracy or time for *focused or calm* users relative to prompt-only GenUI |
| Ablation of the training objective | Component ablations, listed in §6 |
| End-to-end latency breakdown table (ASR, TTFT, decode, TTS, with p50/p90) | Latency table: retrieval, Stage A, Stage B, validation, first paint. Report p50/p90 over the study sessions. |

---

## 5. Frontend: the "Aura Search" window (`search_ui/`, new React + Vite + TS + Tailwind app)

**Setup**
- Scaffold with the same stack as the webcam app: React 18, Vite 6, Tailwind v4, lucide-react.
- Port the files listed below from `HCI Mood assignment/frontend/src/`; do not import from there.
- Visually match Aura's palette: `CALM`, `MILD` and `ELEV` from `run.py:47-55`.

**Window layout**
- A header with the Aura stress gauge chip (live via `/ws/state`) and a state label with confidence.
- The query box.
- The generated results area.
- A "Standard view" toggle and a "Why this layout?" drawer.
- **Single-purpose:** no commerce or workspace tabs.

**`hooks/useTypingDynamics.ts`**
- `keydown`/`keyup` on the search input only.
- Records timestamps and key class (normal, backspace, repeat, ctrl+backspace), mirroring `telemetry_daemon.on_press` weights 0/1/3/4. **It never records characters.**
- Computes the 5 s window features and POSTs them about once a second.

**`components/search/`**
- `SearchView.tsx`: query box, state chip, skeleton, then the rendered spec. Has a "Standard view" toggle and "Why this layout?".
- `GenUISearchRenderer.tsx`: `type → widget` map, in the same pattern as `GenerativeWorkspace.renderNode` (73-154) and the region layouts (232-279).
- Widgets: `AnswerCard`, `KeyFactsList`, `GuidedSteps`, `ComparisonTable`, `ProsCons`, `Timeline`, `SourceList`, `FacetChips`, `FollowUpChips`, `ClarifierChips`, `QueryTrail`.
  - Reused as they are: `SomaticResetWidget` (breathing nudge) and `ContextAnchorBanner`.
  - Read-aloud reuses `speechSynthesis` from `CommerceAgentView`.
- `CustomWidgetFrame.tsx`: `<iframe sandbox="allow-scripts" srcdoc=…>` with no same-origin access, a CSP meta tag blocking network, and fixed max height. It only renders when the validator allows it.

**Ported and adapted from the webcam app**
- `CoPilotProposalBar`, for re-layout proposals.
- `XaiInspectorDrawer`, reduced to a "Why this layout?" view with these tabs:
  - **state:** signal contributions, Aura stress, optional circumplex;
  - **policy;**
  - **raw spec.**
- `useBehavioralTelemetry`: rage-click and hesitation detection, with the `pauseMs` bug fixed (L95/L107). Its counts now feed fusion.
- `PostTaskSurveyModal` (SUS, SAM, NASA-TLX), plus 3 Likert items: perceived personalization, perceived control, trust.
- The `.aura-target` / `.aura-readable` CSS-variable classes from `index.css`.

**Study task runner in Aura, not in a web lab tab**
- Aura's existing Record, Privacy and condition flow stays the study controller.
- A small "Study tasks" picker in the search window loads a task preset (prompt, fixture set, time limit) and opens the survey on finish.

---

## 6. Phased roadmap

| Phase | Deliverable | Done when |
|---|---|---|
| 0 | Host plumbing (§3): `StressEngine` extracted, `LiveState` snapshot, server thread, token, pywebview window, button, tray and hotkey, `complete_json`, `search_ui` scaffold | `python run.py` behaves exactly as before. The Search button opens a window showing the live Aura stress score. `experiments/run_experiment.py` still runs. |
| 1 | Retrieval (Tavily + fixtures) and Stage A, minimal `SearchView` | A query returns a cited TL;DR and claims, also offline via fixtures |
| 2 | Query-typing hook, `state_fusion`, `policy` | The state chip follows Aura's Simulate Stress and Demo modes, plus real typing, with the camera off |
| 3 | Stage B composer, validator, widget library, sandboxed custom slot | The same query under 5 simulated states gives 5 structurally different, valid specs with identical claim sets |
| 4 | `context_window` and the silent-by-default anticipation policy in all 3 modes (reactive, deferred, continuous): clarifiers, struggle detection, re-layout proposals, follow-ups | A reformulation or sustained stress produces exactly one proposal; calm traces stay silent; accept and undo work |
| 5 | Research: new `research.py` record types, consent v4, exports, study-task presets with recorded fixtures, survey, `study_metrics.py` | A full recorded mock trial (consent, then Record, then 3 tasks, then survey, then Journal) verifies its hash chain and exports clean CSVs |
| 6 (optional) | Camera sensor `[vision]` ported into `backend/vision/`, fixed-rate tick, off by default | Turning the camera on adds valence to fusion; turning it off releases the device immediately |
| 7 | Packaging (`AuraUI.exe` with `search_ui/dist`) and the user study and write-up | The exe opens search with no Python installed |

### Study design (Phase 7)

- **Design:** within-subjects, counterbalanced. Conditions:
  - **C0** classic links;
  - **C1** prompt-only GenUI (Stage B, neutral policy);
  - **C2** state-aware GenUI.
  - C1 vs C2 isolates the contribution of user state, which is the core claim.
- **Tasks:** fact-finding and decision tasks with recorded fixtures. Half run under a time-pressure induction, as in Crescenzi 2015.
- **Participants:** about 12–20.
- **Measures:**
  - task time and accuracy (ISO 9241-11);
  - SUS, NASA-TLX, SAM;
  - perceived personalization, control and trust;
  - reformulations, backtracks, proposal acceptance rate;
  - Δ stress (typing) and Δ valence (camera).
- **Offline evaluation:** layout divergence across states for the same query, and a **truth-invariance rate**: the share of Stage B specs whose claim IDs are all in Stage A, with a target of 100%.
- **Research questions:**
  - **RQ1:** Does state-aware GenUI improve efficiency, workload and satisfaction over prompt-only GenUI under stress?
  - **RQ2 (non-inferiority):** Does it avoid harming calm or focused users?
  - **RQ3:** Which signals matter? Answered by the ablations below.
  - **RQ4:** Does proactive timing help? Measured by proposal acceptance, false-intervention rate, missed-struggle rate and time-to-help.
- **Ablations**, run offline on the scenario set and on logged sessions:
  - without fusion (prompt-only);
  - camera only;
  - typing only;
  - behaviour only;
  - without the anticipation loop (reactive only);
  - without the stage split (a single-pass LLM, measuring how truth invariance drops).

---

## 7. Verification

- **Unit tests** (in `tests/test_pipeline.py` style, plus a new `tests/test_search.py`):
  - Typing-feature parity: the same synthetic event sequence through the browser-side feature maths (mirrored in a Python test helper) and `TelemetryDaemon.get_features` gives equal dicts.
  - `StressEngine` behaves identically after extraction: the same feature sequence gives the same scores and tiers as before.
  - Fusion with the camera off (the default) or on; search stays silent while `breathing_active` is set.
  - Every state's policy caps are enforced by the validator.
  - The validator rejects unknown widgets and unknown claim or source IDs.
  - Custom HTML is stripped when the policy disallows it.
  - Struggle detector fires on a reformulation.
  - The decision policy returns `silent` on a steady calm trace, and fires exactly once on a sustained-struggle trace (no repeated firing).
  - The context window caps the LLM input at M groups.
- **API tests** via FastAPI `TestClient`, with `FixtureProvider` and the LLM forced offline so no network is needed:
  - `/api/search` for each of the 3 conditions;
  - `/rerender` keeps the Stage A claim set unchanged;
  - `/compare` returns 6 distinct topologies;
  - requests without the launch token get 401;
  - `research.verify_session` passes on a session containing search records, and `export_dataset` writes the new CSVs.
- **Frontend:** `npm run build` in `search_ui/` passes with no TypeScript errors.
- **Manual end-to-end:**
  1. `python run.py`, then click Search (or press the hotkey). The window opens.
  2. Search a fixture query.
  3. Use Aura's **Simulate Stress** and **Demo** stages to drive state. Check layout changes, the single proposal, accept and undo, "Standard view", and sandbox iframe isolation.
  4. Switch Aura to **Control (A)**: search becomes prompt-only.
  5. Repeat with a live Tavily key.
  6. Dev mode: `python -m backend.search.server --standalone` opened in the browser pane.
- **Latency budget:** skeleton under 150 ms; Stage A under 6 s on free OpenRouter models; re-render under 3 s. Timings are logged in the `search` records.
- **Regression:** Aura still launches, calibrates, records, syncs and runs all interventions after `StressEngine` is extracted and the server thread is added. The server shuts down cleanly on Quit.
