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
  - **C1, prompt-only:** Aura's **Mode: Control (A)**. Results are generated with the neutral layout rules; the LLM is never told the user's state; no offers. State is still computed and logged.
  - **C2, state-aware:** Aura's **Mode: Active (B)**. Layouts follow the fused state, with offers to re-lay out.
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

1. Run `AuraUI.exe`, or `python run.py` from a checkout.
2. Put a `secrets.json` beside it with `openrouter_api_key`. Add `tavily_api_key` for live web results; study tasks use recorded sources, so Tavily is optional during sessions.
3. **Privacy:** enter the participant code and decide with the participant whether to keep the words of their searches (checkbox). Then **Save consent** (consent v4).
4. **Calibrate** (30 s typing baseline). The search box uses the same baseline.
5. *(Optional)* Turn the camera on from the search window. This needs `pip install ".[vision]"` and isn't available in the exe. Tell the participant the video never leaves the computer.

## 4. Session procedure (about 45 minutes)

1. Briefing and consent (5 min).
2. Calibration (1 min). A practice search on a neutral topic (2 min).
3. For each block:
   1. Set **Mode** in Aura (C1 = Control A, C2 = Active B).
   2. Tick **Record session**. The search window's **Study** panel shows *● recording in Aura*.
   3. For each of the 3 tasks: **Start** it, then the participant searches in their own words. In C2, they may accept or decline offers, and use **Standard view** if they like. They click **I'm done** and answer the post-task questionnaire (success, SAM, NASA-TLX, personalization, control, trust, optional answer).
   4. **Usability questionnaire (SUS)** once per block.
   5. Untick **Record session**. Aura's Journal opens: the participant sets perceived stress and mood (0–10) and **Save entry**. This ends the session file.
4. Debrief (5 min): which layouts helped or annoyed, and whether offers came at the right time.

Facilitator rules:
- Do not mention states or layouts before the debrief.
- Do not help with tasks.
- Note any software issue against the block and time.

## 5. Data produced

There is one hash-chained `.jsonl` per block in `data/sessions/<pseudonym>/`. Check every file with `research.verify_session(path)` or `research.audit()`.

`research.export_dataset('exports/')` writes:

| File | One row per | Key columns |
|---|---|---|
| `sessions.csv` | block | condition, duration, mean and peak stress, time per tier, self-report, journal |
| `ticks.csv` | 3 Hz stress tick | score, tier, typing and mouse features |
| `searches.csv` | search | query (or hash), task_id, adaptive, policy, state, confidence, stress, camera valence and arousal, reformulation, query_uncertain, widgets, topology, claims shown, unsupported phrases removed, stage timings, query-typing kps and error rate |
| `search_events.csv` | decision or interaction | proposal, accept, dismiss, undo, expired, counterfactual (C1), standard/adapted view, backtrack, rage_click, hesitation, camera on/off; with target, from and latency |
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

Replay logged `searches.csv` rows through `backend/search/state_fusion.fuse()` with signals removed: Aura stress only, query typing only, behaviour only, camera only. Compare the inferred states with:
- the full-fusion state; and
- the participant's SAM ratings for that task.

Use the dev comparison view (`?dev=1`, then **Compare this search across all states**) for figures showing the same facts in six layouts.

## 8. Ethics and data handling

- Consent v4 covers search queries, task answers and questionnaires. Participants can choose hashed queries. Withdrawal (**Privacy → Withdraw**) deletes local sessions and cloud copies.
- Data is pseudonymous (salted code). The salt and `secrets.json` are never exported.
- Retention: `research.purge_expired(180)`.
- Before the study, tell participants:
  - the camera is optional;
  - the app may *offer* a different layout but never changes it without their click;
  - they can always use **Standard view**.
