# Aura UI — Phase 2 Experiment Report
### Instrument characterisation of a peripheral-telemetry stress monitor

**Course:** Human-Computer Interaction (HCI) · **Institution:** Institute of Business Administration (IBA)
**Team:** Sharique Baig · Maira Aijaz · Barkhi Khan
**Date of run:** 14 November 2026 · **Report version:** 2.0 · **Protocol:** `2.0`

---

## 1. Experiment Title and Objective

**Title:** *Does a peripheral-telemetry stress score discriminate cognitive-load conditions, and how fast and how stably does it do so?*

The Aura UI system infers cognitive load from keystroke dynamics and mouse activity and maps it to a stress score (0–100) and one of three tiers — **Calm** (0–29), **Mild** (30–59), **Elevated** (60–100) — which drive ambient interventions. Before a human-subjects pilot can be justified, the *instrument itself* must be characterised: we must know whether the score actually separates different input regimes, what detection latency and recovery lag it has, whether the deployed tier threshold is defensible, and whether the data-collection pipeline is privacy-safe.

**Objectives**

1. **O1 — Discrimination.** Quantify how well the score separates four controlled input conditions (rest, calm typing, mild load, elevated load).
2. **O2 — Responsiveness.** Measure detection latency and recovery time.
3. **O3 — Threshold validity.** Test whether the deployed Elevated cut-off (score ≥ 60) is empirically supported.
4. **O4 — Data integrity and privacy.** Demonstrate that the new collection subsystem records only permitted numeric data, is consent-gated, pseudonymous, tamper-evident and stored locally.

**Scope note (important):** this experiment characterises the *measurement instrument*, not human stress. Stimuli are controlled input regimes (synthetic typing/mouse telemetry) replayed through the unmodified production scoring engine. **No human participants were involved**, and no claim is made here about physiological or subjective stress validity — that is the role of the human pilot study specified in Phase 1.

---

## 2. Experimental Methodology

### 2.1 System under test

The production path, unmodified:

```
condition features → TelemetryDaemon feature schema → StressEngine.update()
                   → score (0–100) / tier (0–2)     → ResearchCollector (consent-gated)
```

| Component | Source | Role |
|---|---|---|
| `StressEngine` | `run.py` | Production scoring: CoV of flight times, error (backspace) rate, dwell penalty, mouse-jitter penalty, exponential smoothing (α = 0.18) |
| `Settings` | `run.py` | Default parameter set (no per-person calibration; `baseline_cov = baseline_err = 0`) |
| `ResearchCollector` | `backend/research.py` | **New**: consent gate, pseudonymisation, hash-chained JSONL, session summary, export |
| Analysis | `experiments/run_experiment.py` | Protocol driver, metrics, figures |

Because the engine is called exactly as the app calls it, the measured behaviour is the behaviour a user experiences.

### 2.2 Design

- **Design type:** balanced repeated-measures, fixed-order-randomised within rounds (seeded).
- **Conditions:** 4 (`REST`, `CALM`, `MILD`, `ELEV`), each defined by a feature vector (Table 1).
- **Structure:** 5 rounds × 4 conditions = 20 blocks; **20 s per block**; balance ensures each condition appears once per round, so ordering and carry-over effects are spread evenly.
- **Sampling:** one score per 333 ms — the app's own poll interval (`AmbientApp.POLL_MS = 333`) — producing **1,200 observations** over **400 s** of protocol time.
- **Noise:** ±8 % uniform jitter on every feature, so CoV and error-rate estimates vary as they do in live telemetry.
- **Determinism:** `random.Random(20261114)`; identical re-runs reproduce the dataset exactly.
- **No calibration:** a fresh-install configuration (`is_calibrated = 0`) was used deliberately, so results reflect the out-of-the-box experience.

**Table 1 — Condition definitions (inputs to the engine)**

| Condition | Keys/s | Error rate | Mean dwell | Mean flight | Flight-time CoV | Mouse px / 5 s | Clicks / 5 s | Expected tier |
|---|---|---|---|---|---|---|---|---|
| REST | 0.0 | 0.00 | 0 ms | — | — | 0 | 0 | Calm |
| CALM | 4.2 | 0.02 | 95 ms | 140 ms | 0.22 | 1,800 | 3 | Calm |
| MILD | 5.6 | 0.08 | 160 ms | 100 ms | 0.45 | 5,200 | 9 | Mild |
| ELEV | 7.8 | 0.19 | 240 ms | 70 ms | 0.62 | 14,000 | 24 | Elevated |

Ground truth per tick is the condition's expected tier; `REST` exercises the engine's idle-decay path rather than the scoring formula.

### 2.3 Analysis techniques

- Per-condition score statistics (mean, SD, median, p95, min, max).
- **Tier confusion matrix** (condition × predicted tier), accuracy, and two error rates that matter operationally: *Elevated recall* and *false-Elevated rate* during rest/calm.
- **Latency:** time from block onset to the first tick in the Elevated tier, for each `ELEV` block.
- **Recovery:** time from `ELEV` → `REST` transition until the first Calm-tier tick.
- **ROC analysis** of the raw score as an Elevated detector (`ELEV` vs `REST+CALM`), with the operating point chosen by **Youden's J**, and a direct test of the deployed rule at score ≥ 60.
- **Privacy audit:** hash-chain verification, a field-whitelist probe (attempting to store a typed character and a window title), and a consent-gate check.

### 2.4 Tools

Python 3.12.10 · matplotlib (analysis/figures) · the app's own dependencies (pynput, screen-brightness-control, pystray, Pillow, spotipy). All computation local; no network calls in the experiment or the collector.

---

## 3. Data Collection

### 3.1 What was collected

One instrumented session, **1,200 tick records** plus a header and a summary record (**1,202 chained records**). Per tick:

| Group | Fields |
|---|---|
| Timing / state | `t` (s), `score` (0–100), `tier` (0–2), `label` (condition) |
| Typing features | `keys_per_second`, `error_rate`, `mean_dwell`, `std_dwell`, `mean_flight`, `std_flight`, `flight_count` |
| Mouse features | `mouse_distance`, `mouse_clicks` |
| Intervention state | `brightness`, `breathing`, `simulated` |

Per session (summary): duration, tick count, mean/peak score, peak time, seconds per tier, Elevated episodes, breathing prompts, notifications held, and an optional **post-session self-report** (perceived stress 0–10, mood 0–10).

### 3.2 Participants

**Zero human participants.** n = 1 automated session on one operator machine (Windows 11), 1,200 observations, 20 blocks. Human n is deferred to the Phase 1 pilot; the schema and UI are already ready for it (self-report scales are wired into the journal).

### 3.3 Privacy and security design (O4)

The collection subsystem (`backend/research.py`) enforces six properties:

| Property | Mechanism | Verified |
|---|---|---|
| **Consent gate** | `ResearchCollector` raises `PermissionError` unless a versioned consent record exists; the app opens the consent dialog instead of recording | Yes — consent record required before any write |
| **Local only** | No network code in the module; data lives in `data/` on this machine and is git-ignored | Yes — code audit |
| **Pseudonymity** | Participant code → salted SHA-256 (16 hex chars); per-install random salt in `data/.salt`, never exported | Yes — stored id `12d67ce15aaaa520` |
| **Data minimisation** | Strict field whitelist; anything else is dropped before disk. No characters, key codes, window titles, app names or journal text | Yes — probe (below) |
| **Tamper evidence** | SHA-256 hash chain (`prev → h`) over every record | Yes — 1,202/1,202 verified |
| **Retention / withdrawal** | `purge_expired(180 days)`; in-app "Withdraw + delete" purges all sessions | Yes — revocation purge exercised before the run |

**Minimisation probe.** A collector was asked to store `keys_per_second`, `key_char: "a"` and `window_title: "secret.docx"`. On-disk result: `key_char_stored = False`, `window_title_stored = False`, whitelist retained only `keys_per_second`. The probe file was then deleted so it could not contaminate the dataset.

> **Security caveat (stated honestly):** this is *privacy-by-design* data handling on a local workstation, not cryptographic protection at rest — an attacker with file-system access can read the JSONL. POSIX `0600` permissions are applied best-effort and are largely ineffective on Windows ACLs. Encrypting the store (e.g. DPAPI/age) and a Windows ACL pass are recommended before multi-participant deployment.

### 3.4 Dataset manifest

| File | Rows | Notes |
|---|---|---|
| `Phase_2_Submission/data/ticks.csv` | 1,200 | De-identified export; one row per tick |
| `Phase_2_Submission/data/sessions.csv` | 1 | Session summary; no direct identifiers |
| `Phase_2_Submission/results.json` | — | All computed metrics, protocol definition, audit results |
| `data/sessions/<pseudonym>/*.jsonl` | 1,202 records | Local, git-ignored, hash-chained source of truth |

---

## 4. Results and Observations

### 4.1 Discrimination (O1)

**Table 2 — Score per condition (n = 300 ticks each)**

| Condition | Mean | SD | Median | p95 | Min | Max |
|---|---|---|---|---|---|---|
| REST | 25.5 | 29.7 | 10.0 | 88.0 | 0.0 | 98.5 |
| CALM | 18.6 | 7.8 | 16.2 | 32.3 | 11.2 | 85.0 |
| MILD | 44.7 | 7.5 | 45.7 | 49.0 | 8.8 | 90.2 |
| ELEV | 93.6 | 14.6 | 99.8 | 100.0 | 18.0 | 100.0 |

![Score response to controlled conditions](figures/f1_protocol_timeline.png)

*Figure 1 — Score across the full 400 s protocol with condition bands and tier thresholds. Transitions are sharp on entry and visibly slower on exit.*

![Score distribution per condition](figures/f2_score_by_condition.png)

*Figure 2 — Distributions. CALM and MILD are tight; REST is bimodal (carry-over vs settled); ELEV is censored at 100.*

**Table 3 — Typing/mouse features recovered from the recorded stream**

| Condition | Keys/s | Error rate | Mean dwell | Flight CoV | Mouse px / 5 s | Clicks / 5 s |
|---|---|---|---|---|---|---|
| REST | 0.00 | 0.000 | 0 ms | 0.00 | 0 | 0.0 |
| CALM | 4.19 | 0.020 | 95 ms | 0.220 | 1,804 | 2.5 |
| MILD | 5.59 | 0.080 | 160 ms | 0.449 | 5,222 | 8.5 |
| ELEV | 7.80 | 0.189 | 239 ms | 0.621 | 13,957 | 23.4 |

![Typing features per condition](figures/f4_typing_features.png)

*Figure 3 — All four typing features move monotonically with load, confirming the feature layer preserves the intended contrast.*

### 4.2 Tier classification (O1, O3)

**Table 4 — Condition × predicted tier (counts; row % in brackets)**

| Condition | Calm | Mild | Elevated |
|---|---|---|---|
| REST | 198 (66.0 %) | 50 (16.7 %) | 52 (17.3 %) |
| CALM | **282 (94.0 %)** | 15 (5.0 %) | 3 (1.0 %) |
| MILD | 14 (4.7 %) | **279 (93.0 %)** | 7 (2.3 %) |
| ELEV | 2 (0.7 %) | 13 (4.3 %) | **285 (95.0 %)** |

![Confusion matrix](figures/f3_confusion.png)

*Figure 4 — Row-normalised tier prediction by condition.*

Overall accuracy: **87.0 %** (1,044 / 1,200). CALM, MILD and ELEV are each correct ≥ 93 % of the time; almost all error sits in REST.

### 4.3 Detection performance, latency and recovery (O2, O3)

**Table 5 — Detection metrics**

| Metric | Value |
|---|---|
| AUC (score as Elevated detector) | **0.980** |
| Youden-optimal threshold | **score ≥ 60** (TPR 0.95, FPR 0.092) |
| Deployed rule (score ≥ 60) | TPR **0.95**, FPR **0.092** — identical to optimum |
| Elevated recall | 95.0 % |
| False-Elevated rate during REST/CALM | **9.2 %** (55 / 600 ticks) |
| Detection latency (5 ELEV blocks) | 1.00, 1.33, 1.33, 0.33, 1.00 s → **mean 1.00 s** (median 1.00, range 0.33–1.33) |
| Recovery to Calm after ELEV → REST | **15.33 s** in both observed transitions |
| Elevated episodes detected | 5 (one per ELEV block) |

![ROC curve](figures/f5_roc.png)

*Figure 5 — ROC of the raw score. The deployed 60-point cut sits on the empirical optimum.*

---

## 5. Analysis and Discussion

**The score discriminates the conditions cleanly.** Means are 18.6 (CALM) < 44.7 (MILD) < 93.6 (ELEV), each inside its intended band, with low within-condition variance for CALM (SD 7.8) and MILD (SD 7.5). An AUC of 0.980 means a randomly chosen elevated tick outranks a randomly chosen rest/calm tick 98 % of the time. For an instrument fed only by keyboard/mouse rhythm, this is strong separation — and it is achieved with the *unmodified* production formula and no per-person calibration.

**The deployed threshold is defensible.** Youden's J selects exactly score ≥ 60, the cut already hard-coded for tier 2. The threshold was set by design intuition; this run provides the first empirical justification for it. That is a useful, quotable result for the paper: *the tier boundary is not arbitrary.*

**Detection is fast; recovery is slow — and that asymmetry is the main finding.** Entering Elevated takes about 1 s (three polling ticks), because CoV, error-rate, dwell and mouse penalties all fire together and push the smoothed score past 60 almost immediately. Leaving Elevated takes ~15 s. The engine's idle path decays at `decay_speed × 1.5` per tick and only once input falls below 0.2 keys/s *and* 3,000 px, so the tail is long.

The operational consequence is concrete: **9.2 % of all rest/calm ticks were labelled Elevated, and essentially all of them are this tail.** Figure 1 shows it plainly — every `ELEV → REST` transition glides down through the 60 and 30 lines instead of stepping. In the app this means the breathing guide and Focus-mode notification blocking stay active for roughly 15 s after the user has already stopped working, and a "recovery" summary toast fires late. Since the intervention is *supposed* to withdraw as the user calms, the release path is currently the weakest link in the adaptive loop, not the detection path. Recommended remedies: raise `decay_speed` for the release path, add hysteresis (e.g. leave Elevated at ≤ 45), or shorten the idle-detection gate — each testable with this same protocol.

**The ceiling compresses information at the top.** ELEV has median 99.8, p95 100.0 and SD 14.6 with min 18.0; the raw score saturates because `cov/1.0` and `err/0.15` are capped and the sub-scores sum past 1.0 before clamping. Fine for a three-tier alarm, unhelpful if the paper wants to report *continuous* load; consider a soft (tanh) squash instead of a hard clamp.

**Entry ramps, not steady state, produce the misses.** Of the 15 ELEV ticks not labelled Elevated, 13 are Mild and 2 are Calm — the first ~1 s of each block. That is the expected cost of exponential smoothing and is the mirror image of the recovery lag: the same α that filters noise delays both edges.

**REST is the only genuinely noisy condition** (mean 25.5, SD 29.7, p95 88.0) and its spread is entirely carry-over: blocks that begin right after an ELEV block start at ~90 and decay through the block, while settled blocks sit near 0–10. It is therefore *not* evidence of false alarms in normal use — it is the 15 s release lag measured from the other side.

**Typing features behave monotonically.** Keys/s 4.2 → 7.8, dwell 95 → 239 ms, CoV 0.22 → 0.62, error rate 2 % → 19 % (Table 3, Figure 3). The CoV ordering matches the literature intuition that timing variability rises with load; dwell rising with keys/s is the physically expected "heavier, faster" pattern. These are the numbers a human study should correlate against NASA-TLX and self-reported stress.

### Threats to validity (stated explicitly)

1. **Construct validity — the central limitation.** Inputs are synthetic. The mapping "fast erratic typing = stress" is assumed by construction, so this experiment cannot show the score tracks *felt* stress. It shows the instrument does what it is designed to do, reliably.
2. **External validity.** n = 1 session, one machine, one seed, one platform (Windows), no participant variability, no test–retest.
3. **No calibration.** `baseline_cov = baseline_err = 0` (fresh install). A calibrated participant shifts the CoV term and would change absolute scores, likely lowering REST/CALM values.
4. **Interventions disabled.** Brightness/Spotify actions were not exercised (display left untouched); their feedback on the loop is untested here.
5. **Sampling differences.** Real `pynput` telemetry is noisier and sparser than the replay (e.g. `std_dwell` is unavailable in replay), so live CoV stability may be lower than measured.

---

## 6. Conclusion

**Objectives achieved.**

- **O1 — Discrimination: met.** 87.0 % three-class agreement, AUC 0.980, ≥ 93 % per-condition accuracy for CALM/MILD/ELEV. The score separates the intended regimes cleanly with the production formula and no calibration.
- **O2 — Responsiveness: met with one caveat.** Detection latency is ~1.0 s, well within interactive limits. Recovery is ~15.3 s, which is slow enough to keep interventions (breathing guide, notification blocking) active after the user has stopped — the clearest design defect surfaced by this study.
- **O3 — Threshold validity: met.** The deployed Elevated cut (score ≥ 60) coincides with the Youden-optimal operating point (TPR 0.95, FPR 0.092).
- **O4 — Integrity and privacy: met.** Consent-gated, pseudonymous, local-only, hash-chained storage: 1,202/1,202 records verified, disallowed fields (typed character, window title) provably rejected, withdrawal/purge exercised.

**What this experiment does not establish.** That the score measures human stress. The instrument is internally valid and fast; its *construct* validity still requires the within-subjects human pilot (A/B ambient intervention vs. control, NASA-TLX, SUS, self-report, recovery telemetry) already specified in Phase 1. This report is the methodological and infrastructural prerequisite for that step, and the collector it validates is exactly what that pilot will use — including the post-session self-report scales, which are the bridge from synthetic to human data.

**Concrete next actions.** (1) Tune the release path (`decay_speed` / hysteresis) and re-run this protocol to confirm the false-Elevated rate drops from 9.2 % toward < 3 % without hurting latency. (2) Re-run with calibration enabled and compare. (3) Run the human pilot, correlating score with NASA-TLX and self-reported stress. (4) Add encryption at rest and a Windows ACL pass before multi-participant deployment.

---

## Appendix A — Reproducing this experiment

```bash
python -m pip install -r requirements.txt matplotlib
python experiments/run_experiment.py        # consent → protocol → analysis → figures
```

Re-running purges the previous session (withdrawal path), re-consents, replays the seeded protocol and rewrites `results.json`, `data/*.csv` and `figures/*.png`.

## Appendix B — Collecting data from real participants in the app

1. Launch `python run.py` → **Privacy** → enter a participant code → **Save consent** (the full consent text is shown and stored with the record).
2. Tick **Record session**; work normally.
3. To close a session, open **Journal** → set *Perceived stress* and *Mood* → **Save entry**. The summary is written with the self-report attached.
4. **Withdraw + delete** removes every stored session from the machine.

## Appendix C — Package contents

```
Phase_2_Submission/
├── experiment_report.md          this report
├── results.json                  all metrics, protocol, audit results
├── data/ticks.csv                1,200 de-identified tick rows
├── data/sessions.csv             1 session summary row
└── figures/                      f1 timeline · f2 distributions · f3 confusion
                                  f4 typing features · f5 ROC
```

Source added for this phase: `backend/research.py` (collector), `experiments/run_experiment.py` (protocol + analysis), plus consent/self-report UI wiring in `run.py`.
