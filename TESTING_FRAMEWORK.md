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

Before starting each 12-minute session, verify the checkboxes in the Aura UI window match the assigned condition:

| Aura UI Control | **Condition A: Control (Baseline)** | **Condition B: Intervention (Aura Active)** |
| :--- | :--- | :--- |
| **`Privacy` → Consent** | Granted (`Save consent`) | Granted (`Save consent`) |
| **Mode Button (next to Calibrate)** | **`Mode: Control (A)`** *(automatically suppresses all interventions, popups & DND, and tags `condition="control"` in `sessions.csv`)* | **`Mode: Active (B)`** *(enables all selected interventions & tags `condition="intervention"` in `sessions.csv`)* |
| **`Record session`** | **Checked (ON)** *(displays `● Rec MM:SS` timer)* | **Checked (ON)** *(displays `● Rec MM:SS` timer)* |
| **`Auto-adjust brightness`** | Automatically bypassed in Control mode | **Checked (ON)** *(dims & warms to 5000K in Mild, 3500K in Elevated)* |
| **`Focus mode`** | Automatically bypassed in Control mode *(shows `passive (Control A)`)* | **Checked (ON)** *(blocks notifications when Stress $\ge 60$; delivers digest on recovery)* |
| **Breathing Guide & Aura Check-In** | Automatically suppressed in Control mode | Active (automatically prompts physiological sigh & check-in on sustained Elevated stress) |
| **Spotify Auto-Volume** *(Optional)* | Automatically bypassed in Control mode | Connected (automatically ducks volume during stress spikes) |

---

## 5. Step-by-Step Controlled Lab Protocol (~35 Minutes per Participant)

### Preparation (Before Participant Arrives)
1. Ensure you are on the branch containing the research pipeline (`git checkout barkhi`).
2. Launch Aura UI:
   ```powershell
   python run.py
   ```
   *(Or run `dist/AuraUI.exe` if using the packaged build).*
3. Prepare the two equivalent 12-minute cognitive stressor tasks (e.g., **Task 1** and **Task 2**: timed debugging exercises or timed analytical synthesis prompts under a visible countdown timer).

---

### Phase 1: Briefing, Informed Consent & Baseline Calibration (3 Minutes)
1. **Briefing:** Explain to the participant that they will perform two 12-minute computer tasks while Aura UI runs in the background. Reassure them that **no typed characters, words, passwords, or window titles are ever recorded**—only typing speed, rhythm, backspace rate, and mouse distance.
2. **Save Consent in the App:**
   * Click **`Privacy`** (located below the brightness slider).
   * Type the participant's code (e.g., `P01`).
   * Have the participant review the consent text and click **`Save consent`**.
3. **30-Second Personal Calibration:**
   * Click **`Calibrate`** on the left panel.
   * The **Baseline Calibration modal** opens automatically with a sample passage and an auto-focused text box.
   * Have the participant type the sample passage at a relaxed, comfortable pace for 30 seconds while watching the progress bar. This saves their personalized `baseline_cov` and `baseline_err`.

---

### Phase 2: Task Session 1 (12 Minutes)
1. **Configure Condition:** Click the **`Mode: Active (B)` / `Mode: Control (A)`** button (next to `Calibrate`) to match the participant's assigned first condition (**Condition A** or **Condition B**).
2. **Start Recording:** Tick **`Record session`**.
   * Verify that the live timer (`● Rec 00:00`) appears on both the checkbox and the stress gauge.
3. **Run Task 1 (12:00 timer):**
   * Have the participant begin the timed cognitive stressor task.
   * **Controlled Distraction Injection:** At **3:00**, **6:00**, and **9:00** on the live `● Rec MM:SS` timer, trigger a synthetic notification by clicking **`Test notification`** in the Aura UI window.
     * In **Condition A (`Mode: Control (A)`)**, the notification will pop up immediately and interrupt them.
     * In **Condition B (`Mode: Active (B)`)**, if the participant is in the Elevated tier ($\ge 60$), Focus Mode will suppress the alert (`Held back +1`) and release a calm summary digest once they return to Calm.

---

### Phase 3: Closing Session 1 & Mid-Study Assessment (3 Minutes)
1. **Stop Recording & Save Self-Report in the Journal:**
   * At the `12:00` mark on the recording timer, **uncheck `Record session`** (or click **`Journal`** directly).
   * Unchecking `Record session` **automatically opens the Session Journal** in finalize mode (`"Session stopped · set your 0-10 ratings and click Save entry to finalize"`).
   * Ask the participant to set the two sliders:
     * **Perceived stress (0–10)**
     * **Mood (0–10)**
   * Optionally type a brief note or click **`Reflect with Aura`**, then click **`Save entry`**.
     > **What happens automatically:** Clicking **`Save entry`** attaches the 0–10 stress/mood ratings and note to the active research session, writes the summary record with `condition="control"` or `"intervention"`, closes the hash-chained `.jsonl` file, and queues it for Firebase Cloud Sync.
2. **Administer NASA-TLX #1:** Have the participant rate Session 1 across the 6 NASA-TLX dimensions (Mental Demand, Physical Demand, Temporal Demand, Performance, Effort, Frustration).

---

### Phase 4: Task Session 2 — Counterbalanced Condition (12 Minutes)
1. **Switch Condition:** Toggle **`Auto-adjust brightness`** and **`Focus mode`** to the opposite condition.
2. **Start Recording:** Tick **`Record session`** to open a new session file.
3. **Run Task 2 (12:00 timer):**
   * Have the participant complete the second equivalent cognitive task.
   * Inject the same 3 controlled notifications at **3:00**, **6:00**, and **9:00**.
   * In **Condition B**, if the physiological sighing prompt (`Take 60s to breathe`) triggers during sustained elevated stress, allow the participant to follow the 3-cycle guided breathwork.

---

### Phase 5: Closing Session 2 & Post-Study Questionnaires (5 Minutes)
1. **Close Session 2 via the Journal:**
   * Click **`Journal`** $\longrightarrow$ have the participant set **Perceived stress (0–10)** and **Mood (0–10)** $\longrightarrow$ label the note (`Condition B - Task 2` or `Condition A - Task 2`) $\longrightarrow$ click **`Save entry`**.
   * Uncheck **`Record session`**.
2. **Administer NASA-TLX #2:** Complete NASA-TLX for Session 2.
3. **Administer System Usability Scale (SUS):** Have the participant complete the 10-item SUS questionnaire (1 = Strongly Disagree to 5 = Strongly Agree) evaluating Aura UI.
4. **Semi-Structured Debrief Interview (3 Questions):**
   * *Q1 (Ambient Display):* "Did you notice the screen brightness dimming and warming to amber during intense moments? Did it feel calming, unnoticeable, or distracting?"
   * *Q2 (Notification Gatekeeper):* "How did holding back notifications during high-focus/high-stress periods compare to receiving them immediately?"
   * *Q3 (Co-Regulation):* "What was your impression of the physiological sighing breathing guide and the post-session Journal reflection?"

---

## 6. Remote / Field Testing Protocol (Using `AuraUI.exe` + Firebase Sync)

In addition to (or instead of) in-person lab sessions, you can distribute Aura UI to participants' own Windows laptops for longitudinal field testing during real coursework or coding:

1. **Build the Zero-Setup Executable:**
   ```powershell
   pip install pyinstaller
   python -m PyInstaller --onefile --noconsole --name "AuraUI" --add-data "aura_defaults.json;." run.py
   ```
2. **Distribute to Testers:**
   * Send each participant `dist/AuraUI.exe` and [`TESTER_NOTES.md`](TESTER_NOTES.md) along with their assigned code (`P01`, `P02`, etc.).
   * Testers do **not** need Python or config files—`aura_defaults.json` is compiled in and automatically authenticates anonymously with your `aura-ui-hci` Firestore database.
3. **Participant Field Workflow:**
   * Participant opens `AuraUI.exe` (clicking *More info → Run anyway* if Windows SmartScreen appears).
   * Clicks **`Privacy`** $\longrightarrow$ enters their assigned code $\longrightarrow$ clicks **`Save consent`**.
   * Ticks **`Record session`** while working on an assignment or coding task.
   * When done, opens **`Journal`** $\longrightarrow$ sets **Perceived stress (0–10)** and **Mood (0–10)** $\longrightarrow$ clicks **`Save entry`**.
   * The **Cloud sync** indicator turns green (`everything uploaded`), sending the pseudonymized summary and tick array directly to your Firebase Firestore collection (`aura_sessions`).

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
After collecting sessions, verify that all recorded `.jsonl` session files have intact cryptographic hash chains:
```powershell
python -c "from backend import research; import json; print(json.dumps(research.audit(), indent=2))"
```
Expected output: `"chain_ok": true, "bad": []`.

### 2. Export All Sessions to Clean CSVs
Run the built-in exporter to convert all local JSONL sessions into two de-identified CSV files:
```powershell
python -c "from backend import research; print(research.export_dataset('human_pilot_export'))"
```
This creates:
* **`human_pilot_export/sessions.csv`**: One row per completed session containing:
  * `session_id`, `pseudonym`, `condition`, `started`, `duration_s`, `ticks`
  * `score_mean`, `score_peak`, `peak_at_s`
  * `calm_s`, `mild_s`, `elevated_s` *(seconds spent in each tier)*
  * `episodes` *(number of times stress entered Elevated)*
  * `breathing` *(breathing guides triggered)*, `notif_held` *(notifications blocked by Focus Mode)*
  * `sr_stress` *(0–10 perceived stress)*, `sr_valence` *(0–10 mood)*
  * `journal_note`, `journal_reflection`
* **`human_pilot_export/ticks.csv`**: Every 333 ms tick across all sessions with `score`, `tier`, `brightness`, `breathing`, and all 9 whitelisted typing/mouse features.

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
