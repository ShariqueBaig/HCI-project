# Aura UI — Human Participation Testing & Experimental Framework

**Course:** Human-Computer Interaction (HCI)  
**Institution:** Institute of Business Administration (IBA)  
**Team Members:** Sharique Baig · Maira Aijaz · Barkhi Khan  

---

## 1. Overview: How Phase 1 and Phase 2 Connect

This document synthesizes the **Phase 1 Pilot Study Proposal** (`Phase_1_Submission/pilot_study_proposal.tex`) and the **Phase 2 Research Infrastructure & Instrument Validation** (`Phase_2_Submission/experiment_report.md`, `backend/research.py`, `backend/firebase_sync.py`) into a complete operational manual for conducting human-subjects testing.

* **Phase 1 (Experimental Design):** Defined the 35-minute within-subjects ($A/B$) counterbalanced study protocol with $N = 8\text{ to }12$ participants, standardized cognitive stressor tasks, controlled distraction injection, NASA-TLX workload assessment, and System Usability Scale (SUS) evaluation.
* **Phase 2 (Software & Privacy Pipeline):** Validated the telemetry instrument (93.3% tier accuracy, AUC 0.994, 1.0s detection latency, 2.0s recovery time) and built the production research pipeline:
  * **Strict Consent Gate:** Sessions cannot record until informed consent and a participant code are saved.
  * **Pseudonymization & Data Minimization:** Salted SHA-256 participant digests (`data/.salt`) and a strict numeric feature whitelist (never recording typed characters, key codes, or window titles).
  * **Tamper-Evident Storage:** Hash-chained local JSONL records (`data/sessions/<pseudonym>/*.jsonl`).
  * **In-App Self-Report:** Perceived Stress (0–10) and Mood (0–10) sliders wired directly into the Session Journal.
  * **Cloud Sync & Zero-Setup Binary:** Automatic background upload to Firebase Firestore (`aura_sessions`) and a standalone `AuraUI.exe` build for field deployment.

---

## 2. Research Question, Hypotheses & Variables

### Research Question
> *Does peripheral sensory attenuation coupled with an intelligent notification gatekeeper mitigate subjective frustration, reduce time spent in elevated cognitive load, and accelerate stress recovery during high-cognitive-load desktop computing?*

### Hypotheses
* **$H_1$ (Workload & Frustration Reduction):** Participants working with active Aura UI interventions (**Condition B**) will report significantly lower perceived frustration on the NASA-TLX subscale and lower in-app Perceived Stress (`sr_stress`, 0–10) compared to the passive baseline control (**Condition A**).
* **$H_2$ (Attention Continuity & Recovery):** Notification suppression and ambient soothing during elevated stress episodes ($\text{score} \ge 60$) will reduce total time spent in the Elevated tier (`elevated_s`) and shorten post-stressor recovery time back to the Calm tier ($< 30$).
* **$H_3$ (User Acceptance & Calm Computing):** Ambient sensory adjustments (screen dimming and warm color temperature shifts) will achieve high usability on the System Usability Scale ($\text{SUS} > 68$) and be perceived as minimally disruptive.
* **$H_4$ (Construct Validity — Linking Phase 2 to Human Data):** The instrument's objective telemetry (`score_mean`, `score_peak`, Flight-Time CoV, and error rate) will positively correlate with participants' subjective NASA-TLX and self-reported stress ratings.

### Independent & Dependent Variables
| Variable Type | Name | Description / Operationalization |
| :--- | :--- | :--- |
| **Independent Variable (Within-Subjects)** | **System Mode** | **Condition A (Control / Baseline):** Passive telemetry logging only; all interventions OFF.<br>**Condition B (Intervention / Aura Active):** Full ambient brightness/warmth shifts, Focus Mode notification gating, and physiological sighing prompts ON. |
| **Dependent Variable (Objective)** | **Stress & Recovery Telemetry** | Mean stress score (`score_mean`), peak score (`score_peak`), duration in Elevated tier (`elevated_s`), episode count (`episodes`), and recovery time back to Calm. |
| **Dependent Variable (Objective)** | **Typing & Mouse Dynamics** | Keystroke flight-time CoV (`std_flight / mean_flight`), backspace `error_rate`, `mean_dwell`, and `mouse_distance`. |
| **Dependent Variable (Subjective)** | **In-App Self-Report** | Post-session **Perceived Stress (0–10)** (`sr_stress`) and **Mood / Valence (0–10)** (`sr_valence`) saved via the Aura Journal. |
| **Dependent Variable (Subjective)** | **NASA-TLX & SUS** | NASA Task Load Index (6 subscales, 0–100) after each condition; System Usability Scale (10 items, 0–100) after completion. |

---

## 3. Participant Recruitment & Counterbalancing ($N = 8\text{ to }12$)

Recruit **8 to 12 participants** (university students or knowledge workers who regularly perform computer-based analytical or writing tasks).

To eliminate order, learning, and fatigue effects, use a **counterbalanced within-subjects ($A/B$) design**:

| Participant ID | Session 1 Code | Session 1 Condition (12 mins) | Task Set 1 | Session 2 Code | Session 2 Condition (12 mins) | Task Set 2 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **P01** | `P01-A` | **Condition A** (Control) | Task 1 | `P01-B` | **Condition B** (Aura Active) | Task 2 |
| **P02** | `P02-B` | **Condition B** (Aura Active) | Task 1 | `P02-A` | **Condition A** (Control) | Task 2 |
| **P03** | `P03-A` | **Condition A** (Control) | Task 2 | `P03-B` | **Condition B** (Aura Active) | Task 1 |
| **P04** | `P04-B` | **Condition B** (Aura Active) | Task 2 | `P04-A` | **Condition A** (Control) | Task 1 |
| **P05** | `P05-A` | **Condition A** (Control) | Task 1 | `P05-B` | **Condition B** (Aura Active) | Task 2 |
| **P06** | `P06-B` | **Condition B** (Aura Active) | Task 1 | `P06-A` | **Condition A** (Control) | Task 2 |
| **P07** | `P07-A` | **Condition A** (Control) | Task 2 | `P07-B` | **Condition B** (Aura Active) | Task 1 |
| **P08** | `P08-B` | **Condition B** (Aura Active) | Task 2 | `P08-A` | **Condition A** (Control) | Task 1 |
| **P09–P12** | *Continue alternating pattern* | | | | | |

> **Tip on Participant Codes:** Entering `P01-A` for Session 1 and `P01-B` for Session 2 in the **Privacy** dialog generates distinct pseudonyms for each condition, or you can use `P01` for both and distinguish them by their `started` timestamp and `notif_held` / `brightness` columns in `sessions.csv` (or note `"Condition A"` / `"Condition B"` in the Journal note).

---

## 4. App Configuration: Condition A vs. Condition B

Before starting each 12-minute session, verify settings in the unified Aura UI (**Setup**, **Wellness**, and **Lab Console (`Ctrl+Shift+L`) → Study**):

| Aura UI Control | **Condition A: Control (Baseline)** | **Condition B: Intervention (Aura Active)** |
| :--- | :--- | :--- |
| **Setup Step 1 / Consent v4** | Granted (**I Consent · Continue**) | Granted (**I Consent · Continue**) |
| **Lab → Study → Condition** | **`Control (A) — Prompt-only`** *(suppresses all sensory interventions, nudges, Focus Assist & adaptive layouts; tags `condition="control"`)* | **`Active (B) — State-aware`** *(enables comfort preferences & adaptive Search layouts; tags `condition="intervention"`)* |
| **Lab → Study → Recording** | **Start Recording** *(automatically locks Lab Console into Participant Blinded Mode)* | **Start Recording** *(automatically locks Lab Console into Participant Blinded Mode)* |
| **Wellness → Screen Comfort** | Automatically bypassed in Control mode | **On** *(dims brightness & warms toward 5000K in Mild, 3500K in Elevated)* |
| **Wellness → Focus Mode** | Automatically bypassed in Control mode | **On** *(silently holds alerts when Stress $\ge 60$; shows calm digest on recovery)* |
| **Breathing & Corner Nudge** | Automatically suppressed in Control mode | Active *(non-focus-stealing corner pill after 15 s sustained Elevated load; unified Physiological Sigh modal)* |
| **Wellness → Audio Easing / Spotify** *(Optional)* | Automatically bypassed in Control mode | **On** *(smoothly eases Windows master volume or Spotify playback during stress spikes)* |

---

## 5. Step-by-Step Controlled Lab Protocol (~35 Minutes per Participant)

### Preparation (Before Participant Arrives)
1. Ensure you are running the main Aura UI from the repository root (`python run.py --lab` opens with Lab Console available; the older v1 Tkinter build is archived in `old_version/`).
2. Or run `dist/AuraUI.exe` if using the packaged build.
3. Prepare the two equivalent 12-minute cognitive stressor tasks (e.g., **Task 1** and **Task 2**: timed debugging exercises or timed analytical synthesis prompts under a visible countdown timer).

---

### Phase 1: Briefing, Informed Consent & Baseline Calibration (3 Minutes)
1. **Briefing:** Explain to the participant that they will perform two 12-minute computer tasks while Aura UI runs quietly in the tray/background. Reassure them that **no typed characters, words outside Search, passwords, or window titles are ever recorded**—only typing speed, rhythm, backspace rate, dwell time, and mouse distance.
2. **Save Consent in Setup Step 1:**
   * In the **Setup & Calibration** wizard (auto-opens on first start, or via the top-right sliders button), enter the participant's code (e.g., `P01`).
   * Have the participant review Consent v4 (including the query-text toggle) and click **`I Consent · Continue`**.
3. **30-Second Personal Calibration (Setup Step 2):**
   * Click **`Start 30s Calibration`**.
   * Have the participant type the highlighted upper passage at their natural pace while live WPM, accuracy, and keystrokes mirror inline. This saves their DPI-normalized personal baseline (`baseline_cov`, `baseline_err`, `baseline_kps`, `baseline_dwell`).
   * Complete Step 3 (**Ambient Comfort Preferences** & theme) and click **`Finish & Open Aura`**.

---

### Phase 2: Task Session 1 (12 Minutes)
1. **Configure Condition:** Open **Lab Console (`Ctrl+Shift+L`) → Study** and select **`Control (A) — Prompt-only`** or **`Active (B) — State-aware`**.
2. **Start Recording:** Click **`Start Recording`**.
   * Lab Mode automatically locks into **Participant Blinded Mode** so experimental condition labels and telemetry internals stay hidden from the participant during work.
3. **Run Task 1 (12:00 timer):**
   * Have the participant begin the timed cognitive stressor task.
   * **Controlled Distraction Injection:** At **3:00**, **6:00**, and **9:00**, unlock Lab temporarily or use **`Test notification`** in **Lab → Sim & Demo**:
     * In **Condition A**, notifications deliver normally.
     * In **Condition B**, if the participant is in the Elevated tier ($\ge 60$), **Silent Focus Mode** holds alerts without interrupting popups and surfaces one calm **Focus digest** banner when load drops.

---

### Phase 3: Closing Session 1 & Mid-Study Assessment (3 Minutes)
1. **Stop Recording & Save Self-Report:**
   * At the `12:00` mark, open **Lab Console (`Ctrl+Shift+L`) → Study** and click **`Stop Recording`**.
   * Stopping opens the explicit **Finish Recorded Session** modal:
     * Set **Perceived stress during this block (0–10)** and **Overall mood (0–10)**.
     * Optionally type a brief note or click **`Reflect with Aura`**, then click **`Save & Finalize`**.
     > **What happens automatically:** Clicking **`Save & Finalize`** attaches the 0–10 stress/mood ratings and note to the active session, closes the hash-chained `.jsonl` file with `condition="control"` or `"intervention"`, and queues it for Firebase Cloud Sync. Saving notes earlier in **Wellness → Session Journal** never stops an active recording.
2. **Administer NASA-TLX #1:** Have the participant rate Session 1 across the 6 NASA-TLX dimensions.

---

### Phase 4: Task Session 2 — Counterbalanced Condition (12 Minutes)
1. **Switch Condition:** In **Lab Console (`Ctrl+Shift+L`) → Study**, unlock Lab and switch to the opposite condition.
2. **Start Recording:** Click **`Start Recording`** (re-engages Participant Blinded Mode and opens a new session file).
3. **Run Task 2 (12:00 timer):**
   * Have the participant complete the second equivalent cognitive task and inject the same 3 notifications at **3:00**, **6:00**, and **9:00**.
   * In **Condition B**, after 15 s of sustained Elevated load, Tier-2 escalation gently offers the non-focus-stealing corner **`AmbientNudgePill`** (**20s sigh**, **Check in**, **Snooze 30m**).

---

### Phase 5: Closing Session 2 & Post-Study Questionnaires (5 Minutes)
1. **Stop Recording & Save Self-Report:**
   * At the `12:00` mark, click **`Stop Recording`** in Lab → Study and complete **Finish Recorded Session** (**`Save & Finalize`**).
2. **Administer NASA-TLX #2** and **System Usability Scale (SUS)**.
3. **Semi-Structured Debrief Interview (3 Questions):**
   * *Q1 (Ambient Display):* "Did you notice the screen brightness/warmth or UI atmosphere shifting during intense moments? Did it feel calming, unnoticeable, or distracting?"
   * *Q2 (Silent Notification Shield):* "How did holding notifications silently until a recovery digest compare to receiving them immediately?"
   * *Q3 (Co-Regulation & Control):* "What was your impression of the corner breathing/check-in suggestion and post-session wrap-up?"

---

## 6. Remote / Field Testing Protocol (Using `AuraUI.exe` + Firebase Sync)

In addition to (or instead of) in-person lab sessions, you can distribute Aura UI to participants' own Windows laptops:

1. **Build the Zero-Setup Executable:**
   ```powershell
   cd search_ui && npm run build && cd ..
   python build_exe.py
   ```
2. **Distribute to Testers:**
   * Send each participant `dist/AuraUI.exe` and [`TESTER_NOTES.md`](TESTER_NOTES.md) along with their assigned code (`P01`, `P02`, etc.).
   * Testers do **not** need Python or config files—`aura_defaults.json`, `search_ui/dist`, and `search_fixtures/` are compiled into `AuraUI.exe`.
3. **Participant Field Workflow:**
   * Opens `AuraUI.exe` → completes the 3-step **Setup** wizard (Consent v4 + 30 s calibration + comfort/theme).
   * Opens **Lab (`Ctrl+Shift+L`) → Study** → clicks **`Start Recording`** while working.
   * When done, clicks **`Stop Recording`** → rates **Perceived stress (0–10)** and **Mood (0–10)** → **`Save & Finalize`**.
   * Uploads pseudonymously to Firebase Firestore (`aura_sessions`).

---

## 7. Questionnaires Quick-Reference

### A. NASA-TLX Subscales (Rate 0–100 after Session 1 and Session 2)
1. **Mental Demand:** How mentally demanding was the task? *(0 = Very Low, 100 = Very High)*
2. **Physical Demand:** How physically demanding/tiring was the typing and mouse activity? *(0 = Very Low, 100 = Very High)*
3. **Temporal Demand:** How hurried or rushed was the pace of the task? *(0 = Very Low, 100 = Very High)*
4. **Performance:** How successful were you in accomplishing what you were asked to do? *(0 = Perfect, 100 = Failure)*
5. **Effort:** How hard did you have to work to accomplish your level of performance? *(0 = Very Low, 100 = Very High)*
6. **Frustration:** How insecure, discouraged, irritated, stressed, and annoyed were you? *(0 = Very Low, 100 = Very High)*

### B. System Usability Scale (SUS — Rate 1 to 5 after Study)
1. I think that I would like to use Aura UI frequently.
2. I found Aura UI unnecessarily complex.
3. I thought Aura UI was easy to use.
4. I think that I would need the support of a technical person to be able to use Aura UI.
5. I found the various functions in Aura UI (ambient dimming, Focus mode, breathing guide, journal) were well integrated.
6. I thought there was too much inconsistency in Aura UI.
7. I would imagine that most people would learn to use Aura UI very quickly.
8. I found Aura UI very cumbersome/intrusive to use.
9. I felt very confident using Aura UI.
10. I needed to learn a lot of things before I could get going with Aura UI.

> **SUS Scoring Formula:** For odd items (1, 3, 5, 7, 9), subtract 1 from the user rating. For even items (2, 4, 6, 8, 10), subtract the user rating from 5. Sum the converted scores and multiply by **2.5** to get a score out of **100** (benchmark average is **68**).

---

## 8. Data Export, Verification & Analysis Playbook

### 1. Audit Tamper-Evident Hash Chains
After collecting sessions, verify hash-chain integrity either directly inside **Lab Console (`Ctrl+Shift+L`) → Study → Data Integrity & Export** or from Python:
```powershell
python -c "from backend import research; import json; print(json.dumps(research.audit(), indent=2))"
```
Expected output: `"chain_ok": true, "bad": []`.

### 2. Export All Sessions to Clean CSVs (or ZIP)
You can export directly from **Lab Console → Study** (**Export CSVs to Folder** → `exports/<timestamp>/` or **Download ZIP** → `aura_study_export.zip`), or via Python:
```powershell
python -c "from backend import research; print(research.export_dataset('human_pilot_export'))"
```
This creates six de-identified CSV files:
* **`sessions.csv`**: One row per completed session (`session_id`, `pseudonym`, `condition`, `started`, `duration_s`, `ticks`, `score_mean`, `score_peak`, `peak_at_s`, `calm_s`, `mild_s`, `elevated_s`, `episodes`, `breathing`, `notif_held`, `sr_stress`, `sr_valence`, `journal_note`, `journal_reflection`).
* **`ticks.csv`**: Every 333 ms tick across all sessions with `score`, `tier`, `brightness`, `breathing`, and all 9 whitelisted typing/mouse features.
* **`searches.csv`**, **`search_events.csv`**, **`tasks.csv`**, and **`surveys.csv`**: Search queries/hashes, adaptive policies, proposals/accepts/undos, task timings, and SAM/NASA-TLX/SUS responses.

### 3. Generate Session Visualization Plots
To generate high-resolution timeline curves (`aura_session_chart.png`) for your report or poster:
```powershell
python plot_session.py
```

### 4. Statistical Comparisons for Your Final Report
Using `sessions.csv` and your NASA-TLX/SUS sheets, report these four core analyses:
1. **Subjective Stress & Workload Reduction ($H_1$):**
   * Compare **Condition A vs. Condition B** on in-app `sr_stress` (0–10) and **NASA-TLX Frustration** (0–100) using a paired *t*-test (or Wilcoxon signed-rank test), reporting Mean $\pm$ SD and percentage reduction.
2. **Objective Stress & Recovery Speed ($H_2$):**
   * Compare **Condition A vs. Condition B** on `score_mean`, percentage of session spent in Elevated stress (`elevated_s / duration_s`), and mean recovery time (seconds to return from $\ge 60$ to $< 30$).
3. **Construct Validity — Telemetry vs. Human Rating ($H_4$):**
   * Compute Pearson $r$ / Spearman $\rho$ correlation between Aura UI's `score_mean` (and Flight-Time CoV) and the participant's self-reported `sr_stress` (0–10) and NASA-TLX score.
4. **System Usability & Acceptance ($H_3$):**
   * Report overall mean **SUS score** (out of 100) alongside qualitative quotes from the post-study interview.
