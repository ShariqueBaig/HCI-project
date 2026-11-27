# Aura Search — user study protocol

Companion to [AURA_SEARCH_PLAN.md](AURA_SEARCH_PLAN.md) (design) and
[TESTING_FRAMEWORK.md](TESTING_FRAMEWORK.md) (Aura's stress-monitor study). This document
describes how to run the Aura Search study with the software as built. Every measure listed
here is produced by the current code.

## 1. Research questions

| RQ | Question | Primary measures |
|---|---|---|
| RQ1 | Does state-aware generated search (C2) improve efficiency, workload and satisfaction over prompt-only generated search (C1) when people are under pressure? | Time on task, ISO 9241-11 efficiency and effectiveness, NASA-TLX, SUS |
| RQ2 (non-inferiority) | Does C2 avoid harming calm or focused searchers? | Same measures, in the no-pressure blocks |
| RQ3 | Which signals matter? | Offline ablations on logged sessions (§7) |
| RQ4 | Does proactive timing help? | Offer acceptance rate, undo rate, time to answer an offer, counterfactual offers in C1 |

## 2. Design

- **Within-subjects** design with two conditions, counterbalanced:
  - **C1, prompt-only:** Set **`Control (A) — Prompt-only`** in **Lab Console (`Ctrl+Shift+L`) → Study**. Results use the neutral (`Standard View`) layout rules; the LLM is never told the user's state; no offers or sensory interventions run. State is still computed and logged silently.
  - **C2, state-aware:** Set **`Active (B) — State-aware`** in **Lab Console (`Ctrl+Shift+L`) → Study**. Layouts and ambient comfort follow the fused state, with gentle proposals when evidence shifts.
  - **C0, classic links (optional baseline):** use the dev comparison view or plain source lists. C0 isn't a separate switch in the app.
- **Time pressure** is crossed with condition, following Crescenzi, Kelly & Azzopardi (SIGIR 2015). In pressure blocks the facilitator says: *"You have 3 minutes for this task; please work as fast as you can."* Play an audible timer.
- **Tasks:** 3 per block, one of each type: explain, compare, how-to. They are recorded in `search_fixtures/`, so every participant sees the same sources whatever words they type. Record additional tasks with:

  ```
  python -m backend.search.providers record "<seed query>" --task "<instruction shown to the participant>"
  ```

  For a 2×2 design (condition × pressure), prepare 4 task sets of 3 and rotate them across cells with a Latin square.
- **Sample:** 12–20 participants (small-n HCI study). Report effect sizes with 95% CIs, not only p-values.

### Counterbalancing (2 conditions × 2 pressure levels)

| Participant # mod 4 | Block 1 | Block 2 | Block 3 | Block 4 |
|---|---|---|---|---|
| 0 | C1 calm | C2 calm | C1 pressure | C2 pressure |
| 1 | C2 calm | C1 calm | C2 pressure | C1 pressure |
| 2 | C1 pressure | C2 pressure | C1 calm | C2 calm |
| 3 | C2 pressure | C1 pressure | C2 calm | C1 calm |

## 3. Setup (per machine)

1. Run `AuraUI.exe`, or `python run.py` from the repository root (`python run.py --lab` starts with the Lab Console visible).
2. Put a `secrets.json` beside it with `openrouter_api_key`. Add `tavily_api_key` for live web results; study tasks use recorded sources in `search_fixtures/`, so Tavily is optional during sessions.
3. **Step 1 — Privacy & Consent:** In the Setup wizard (or **Lab → Consent** / **Wellness → Setup & Privacy**), enter the participant code and choose whether search query text may be stored (unchecking keeps only salted hashes). Click **I Consent · Continue** (Consent v4).
4. **Step 2 — 30-Second Rhythm Calibration:** Complete the interactive typing-passage calibration to capture personal baseline typing speed, dwell time, variability, and error rate.
5. *(Optional)* Toggle the camera on from the Search header. This needs `pip install ".[vision]"` and isn't included in `AuraUI.exe`. Tell the participant video never leaves the computer.
   - Because starting a recording automatically enables **Participant Blinded Mode** (`Lab → Study → Lock`), the Lab Console (`XAI`, `Sim & Demo`, `Engine`), mood tags, quick Moods bar, and model/timing debug footers stay hidden from participants during tasks. Keep them locked until the post-study debrief.

## 4. Session procedure (about 45 minutes)

1. Briefing and consent (5 min).
2. Calibration (1 min). A practice search on a neutral topic (2 min).
3. For each block:
   1. Open **Lab Console (`Ctrl+Shift+L`) → Study** and select the assigned condition (**Control (A) — Prompt-only** or **Active (B) — State-aware**).
   2. Click **Start Recording**. Recording starts and automatically locks Lab Mode into Participant Blinded Mode; the **Study** panel appears in Search.
   3. For each of the 3 tasks: click **Start**, then the participant searches in their own words. In C2, they may accept/dismiss/undo layout proposals and switch views (including **Standard View** escape) anytime from the layout-mode menu. Click **I'm done** and submit the post-task questionnaire (success, SAM, NASA-TLX, personalization, control, trust, optional answer).
   4. Complete the **SUS** questionnaire once per block.
   5. Open **Lab Console (`Ctrl+Shift+L`)** (unlocking if prompted) and click **Stop Recording**. The **Finish Recorded Session** wrap-up modal opens: the participant sets Perceived Stress and Mood (0–10), optionally writes a note, and clicks **Save & Finalize** to close and hash-chain the session file.
4. Debrief (5 min): unlock Lab Console to inspect XAI / telemetry if desired, discuss which layouts helped or annoyed, and review timing of offers.

Facilitator rules:
- Do not mention states or layouts before the debrief.
- Do not help with tasks.
- Note any software issue against the block and time.

## 5. Data produced

There is one hash-chained `.jsonl` per block in `data/sessions/<pseudonym>/`. Verify integrity or export 1-click from **Lab Console (`Ctrl+Shift+L`) → Study → Data Integrity & Export** (**Export CSVs to Folder** / **Download ZIP**), or in Python via `research.audit()` / `research.export_dataset('exports/')`:

| File | One row per | Key columns |
|---|---|---|
| `sessions.csv` | block | condition, duration, mean and peak stress, time per tier, self-report, journal |
| `ticks.csv` | 3 Hz stress tick | score, tier, typing and mouse features |
| `searches.csv` | search | query (or hash), task_id, adaptive, policy, state, confidence, stress, camera valence and arousal, reformulation, query_uncertain, widgets, topology, claims shown, unsupported phrases removed, stage timings, query-typing kps and error rate |
| `search_events.csv` | decision or interaction | proposal, accept, dismiss, undo, expired, counterfactual (C1), standard/adapted view, backtrack, rage_click, hesitation, camera on/off, mood_sim_start/stop; with target, from and latency |
| `tasks.csv` | task start or end | task_id, duration_s, number of searches |
| `surveys.csv` | questionnaire | success, SAM ×3, NASA-TLX ×3, personalization, control, trust, efficiency, effectiveness, SUS items and score, optional answer text |

Cloud sync, if enabled, uploads only aggregates (`search_*` counts and `search_sus_mean`), never queries or answers.

## 6. Analysis plan

- **RQ1/RQ2:** a mixed model per outcome: `outcome ~ condition * pressure + task_type + (1 | participant)`. Use time on task and number of searches from `tasks.csv`, and survey scores from `surveys.csv`.
  - RQ2 is a non-inferiority test in the calm blocks, with a margin set beforehand: SUS −5 points, time +15%.
- **Manipulation check:** pressure blocks should show higher Aura stress (`ticks.csv`) and higher SAM arousal and NASA-TLX.
- **Sensor validity:** Aura's mean stress against SAM arousal per task (`study_metrics.stress_sam_alignment`). Report agreement; do not assume the sensors are right.
- **RQ4:**
  - Offer acceptance = accept / proposal; undo rate = undo / accept.
  - Missed help: C1 `counterfactual` offers with no later self-recovery.
  - Unwanted offers: dismissed or expired offers, plus low "control" ratings.
- **Truth invariance:** the share of searches with `ungrounded_removed = 0`, and the total phrases removed. By construction, every fact shown is a Stage A claim (`claims_shown` ⊆ claims).

## 7. Offline ablations (RQ3)

Exclude any search made between a `mood_sim_start` and its `mood_sim_stop` (or 45 s later) from the analysis. Replay logged `searches.csv` rows through `backend/search/state_fusion.fuse()` with signals removed: Aura stress only, query typing only, behaviour only, camera only. Compare the inferred states with:
- the full-fusion state; and
- the participant's SAM ratings for that task.

Use the dev comparison view (`?dev=1`, then **Compare this search across all states**) for figures showing the same facts in six layouts.

## 8. Ethics and data handling

- Consent v4 covers search queries, task answers and questionnaires. Participants can choose hashed queries. Withdrawal (**Wellness → Setup & Privacy → Manage data → Withdraw & delete data…**, requiring explicit confirmation) deletes local sessions and cloud copies.
- Data is pseudonymous (salted code). The salt and `secrets.json` are never exported.
- Retention: `research.purge_expired(180)`.
- Before the study, tell participants:
  - the camera is optional;
  - the app may *offer* a different layout or gentle corner break suggestion, never forcing modal interruptions;
  - they can always switch back to **Standard View** or toggle **Auto-adapt** off.
