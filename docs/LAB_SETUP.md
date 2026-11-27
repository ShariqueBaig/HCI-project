# Running Aura UI in a lab (multi-station setup)

For a study where 10–12 participants each sit at a station for 20–30 minutes.
Every station is a **lab Windows 10/11 machine**, and audio is the **Windows
system volume** — nobody needs a Spotify account for the intervention to work.

One section per thing that actually goes wrong on the day.

For the printable version — what to set up once for the lab, once per station, and once
per participant — see **[AURA_STATION_GUIDE.pdf](AURA_STATION_GUIDE.pdf)** (source:
`docs/station_setup_guide.html`).

---

## 1. The decisions this setup is built around

| Constraint | Reality | What to do |
|---|---|---|
| **Station OS** | Windows 10/11, 64-bit | All stations are lab Windows machines. Anyone who signed up for macOS/Linux gets moved to a lab station (or dropped) — this build uses Windows APIs for brightness, Focus Assist and volume |
| **Audio** | The Music panel drives the **Windows master volume**, so auto-lower works with Spotify, YouTube, a local player or headphones | Install `pycaw` on every station for exact control. If it is missing, the app falls back to the volume media keys |
| **Spotify** | Optional. A Development-Mode Spotify app allows **5 users** and the owner needs **Premium** | Leave it unlinked unless a participant asks. Linking adds per-track volume and play/pause; it never gates the study |
| **Database** | Firebase Cloud Firestore, project `aura-ui-hci`, collection `aura_sessions`, one anonymous identity per station | Nothing per participant, but every station needs internet. See §7 |

---

## 2. What each station needs

- `AuraUI.exe` (or a source checkout) in a **writable folder** — Desktop or
  `C:\AuraUI`. **Never `C:\Program Files`**: the app keeps its data next to the
  exe and cannot write there.
- **`lab_salt.txt`** in the same folder (see §3) — without it the same
  participant code becomes a *different* pseudonym on every machine.
- Internet.
- `pycaw` for exact system-volume control (`pip install pycaw`, already in
  `requirements.txt`). Without it the app uses the volume media keys, which is
  approximate (2 % steps, and some lab images disable media keys entirely).

Copy the whole folder to each station rather than re-downloading; that is how
`lab_salt.txt` and the station's Firebase identity stay consistent.

---

## 3. One-time setup per station

**On the first station only:**

```bash
python tools/lab_setup.py salt-init
```

That writes `lab_salt.txt`. **Copy that file into every other station's folder.**
It is what makes `P07` mean the same person on station 3 as on station 1, so a
participant's sessions can be joined and deleted together. It never leaves the
lab and never enters an export.

**On every station:**

```bash
python tools/lab_setup.py status      # is the station configured?
python tools/lab_setup.py check       # is it NAMED, and can it really write? (§4)
```

Run it with no arguments (or `--help`) to print the usage and the example commands.

**Or do the whole station in one command** — it finds Python, creates `.venv`, installs
`requirements.txt` (so `pycaw` is there), drops the shared salt in place, then runs
`status` and `check`:

```powershell
powershell -ExecutionPolicy Bypass -File tools\setup_station.ps1 -SaltFrom \\labshare\lab_salt.txt
```

Add `-Code P01` to name the station in the same run, `-Condition control` for the control
arm, and `-Build` to rebuild `dist\AuraUI.exe` with pycaw bundled. `-SkipDeps` (no venv,
no pip) and `-SkipCheck` (no network) keep a re-run fast; `-Force` is passed to `prepare`.
It exits 1 if the check fails, so a lab script can gate on it. Double-clicking
`tools\setup_station.bat` runs the same thing with PowerShell's execution policy bypassed.

`status` should end with something like:

```
  lab salt   : shared (.../lab_salt.txt)
  firebase   : aura-ui-hci / aura_sessions | enabled
  station uid: <some id>            <- proves anonymous sign-in works
  pending    : 0 session(s) waiting to upload
  spotify    : configured | not linked
  audio      : system volume via Core Audio
```

`NOT SET` salt, `sign-in failed`, or `audio: unavailable` are the three things to
fix before participants arrive.

> **Building the exe yourself?** Use `build_exe.py` after building the React frontend so `search_ui/dist`, `search_fixtures/`, `aura_defaults.json`, and `pycaw` are all bundled:
> ```bash
> cd search_ui && npm run build && cd ..
> python build_exe.py
> ```

---

## 4. Testing that a station is named and connected

`status` only reports configuration. `check` proves the two things that
invalidate a session if they are wrong, and it is safe to run at any time
(including mid-study):

```bash
python tools/lab_setup.py check
```

```
Station name
  [ok]   shared lab salt: C:\AuraUI\lab_salt.txt
  [ok]   participant code: P01
  [ok]   pseudonym: e73582e4a42d3d2a
  [ok]   consent on file (2026-11-18T09:31:12+05:00), pseudonym e73582e4a42d3d2a
  condition  : intervention
  [ok]   audio: Windows system volume via Core Audio

Database
  service    : Firebase Cloud Firestore (REST API, Anonymous sign-in)
  project    : aura-ui-hci
  collection : aura_sessions
  console    : https://console.firebase.google.com/project/aura-ui-hci/firestore
  station uid: vlnS1M4Z3SPKu5Xqbi1naVnhcRg2
  [ok]   write test: write + delete confirmed
  pending    : 0 session(s) waiting to upload

Sessions recorded on this station
  e73582e4a42d3d2a   2400 ticks  named, uploaded

[ok] this station is named and can write to Firestore
```

- **Named** means a participant code is set, consent is on file, and both agree
  on the same pseudonym. `[FAIL] no participant code` → run `prepare`.
- **Connected** means the check wrote a one-document marker into
  `aura_sessions` and deleted it again. Sign-in alone does not prove the
  Firestore rules accept writes; this does. `[FAIL] write rejected: HTTP 403` →
  publish the rules in `docs/FIREBASE_SETUP.md`.
- The marker doc is named `_station_probe_<uid>`; if the delete fails the check
  says so and you can remove it in the Firebase console. No participant data is
  involved.

Exit code is `0` only when both halves pass, so it works in a script.

---

## 5. Before each participant (30 seconds)

```bash
python tools/lab_setup.py prepare --code P01 --condition intervention
```

This writes consent, sets the participant code and study arm, clears the previous
participant's journal and **forgets their Spotify login**, then checks Firestore.
It refuses to run if a previous session never uploaded.

`--condition control` for the passive/control arm (no interventions fire; the app
only measures). Record which participants are in which arm — it is written into
every session.

Then the participant:

1. Launches Aura UI (`AuraUI.exe` or `python run.py`).
2. Opens **Lab Console (`Ctrl+Shift+L`) → Study** and clicks **Start Recording** (which automatically locks Lab into Participant Blinded Mode).
3. Plays music however they like — the app controls **Windows system volume**.
   Optionally clicks **Connect Spotify** in the **Wellness** tab if they want per-track control and the account is allowlisted.
4. Works for 20–30 minutes.
5. Opens **Lab (`Ctrl+Shift+L`) → Study → Stop Recording** → sets 0–10 ratings in **Finish Recorded Session** → **Save & Finalize** (finalizes and uploads).

Run `python tools/lab_setup.py check` once after a participant if you want
confirmation of their name before they start work; otherwise `verify` after the
session covers the upload.

---

## 6. Audio: system volume first, Spotify optional

| Panel shows | Meaning | What to do |
|---|---|---|
| `Audio: Windows volume (Core Audio)` | `pycaw` is installed — exact 0–100 control of the default output | nothing |
| `Audio: Windows volume (volume keys)` | no `pycaw`; the app sends media keys | `pip install pycaw`, restart the app |
| `Audio: unavailable` | not Windows, or no audio endpoint | check the machine's audio device |
| `Audio: Spotify` | a participant linked an account; volume and play/pause go through Spotify | nothing |

Auto-lower ramps the master volume down in small steps when the stress tier is
Elevated and back up when it calms. It affects whatever is playing, so music from
a phone connected over Bluetooth or a YouTube tab behaves the same as Spotify.

**Linking Spotify** — the participant clicks **Connect Spotify**; their browser
opens Spotify's own login; they approve. PKCE means no client secret exists
anywhere, and the token is cached per machine. Nothing authenticates until that
button is pressed. `prepare` and `reset` both forget the previous participant's
login.

**Limits** — with a Development-Mode app only the 5 allowlisted Spotify accounts
in *Dashboard → Settings → User Management* can link. The 6th gets *This Spotify
account must be added as a test user*. Since the study does not need Spotify,
the recommendation is simply: **do not link accounts**. If someone insists, add
them to the allowlist before they sit down.

**Playback controls** need an active Spotify device (phone or desktop app open).
If the panel says *Nothing playing*, nothing is broken — there is just no active
device.

---

## 7. Where the data goes — which database

**Firebase Cloud Firestore**, in Google's `asia-south1`-style default database of
the project **`aura-ui-hci`**:

| | |
|---|---|
| Service | Cloud Firestore (Native mode), reached over the Firestore **REST API** |
| Project | `aura-ui-hci` |
| Collection | `aura_sessions` |
| Document id | `<pseudonym>_<session_id>` |
| Auth | Firebase **Anonymous** sign-in, one uid per station, cached in `data/firebase_identity.json` |
| Console | <https://console.firebase.google.com/project/aura-ui-hci/firestore> |
| Endpoint | `https://firestore.googleapis.com/v1/projects/aura-ui-hci/databases/(default)/documents/aura_sessions` |

Nothing needs a service account or an SDK: the app signs in anonymously and POSTs
one document per session. The Web API key in `aura_defaults.json` is public by
design — it identifies the project, and the security rules decide what may be
written (create/delete only where `uid == request.auth.uid`; reads are off).

Each finished session becomes **one document** containing:

- the salted pseudonym and the participant's study condition
- numeric telemetry only (≤ 800 sampled ticks, plus summary and ratings)
- the participant's journal note and Aura's reflection (plus search aggregate metrics under Consent v4)
- `uid` — the station's anonymous identity, checked by the rules
- `chain_ok` — `false` if the local log was damaged (e.g. the machine was killed
  mid-session); such a document is still uploaded but flagged

Doc ids look like `e73582e4a42d3d2a_20261116-165231-6d9b6f`. One participant on
two stations produces one pseudonym across both, as long as `lab_salt.txt` is
identical.

**Local copies** stay in `data/sessions/<pseudonym>/` on the station, plus
`journal.json` and `settings.json`. Keep the folders until the study is written
up; they are your backup if the network died.

**Withdrawal** — **Wellness → Setup & Privacy → Manage data → Withdraw & delete data…** (confirmed) deletes the local files *and* this station's uploaded documents for that pseudonym. On a multi-station lab, run it from each station the participant used.

---

## 8. After each participant

```bash
python tools/lab_setup.py verify
```

```
  <session>.jsonl    2400 ticks  uploaded
  station uid: ...
  pending    : 0
  [ok] every finished session is in Firestore
```

Then reset the station for the next person:

```bash
python tools/lab_setup.py reset          # keeps the session archive
```

If `verify` says **not uploaded**: the app retries every 5 minutes, and
`python -m backend.firebase_sync --push` retries immediately. Sessions are
local-first, so nothing is lost while you sort out the network — the `.synced`
marker is only written after Firestore confirms the write.

---

## 9. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `[warn] no lab_salt.txt` | station missing the shared salt | copy `lab_salt.txt` into the folder, re-run `prepare` |
| `check`: `no participant code` | `prepare` was not run (or `reset` was) | `python tools/lab_setup.py prepare --code P02` |
| `check`: `consent pseudonym does not match` | settings and consent came from different salts/codes | re-run `prepare` |
| `check`: `write rejected: HTTP 403` | Firestore rules not published, or too strict | publish the rules in `docs/FIREBASE_SETUP.md` |
| `check`: `cannot reach Firestore` | no internet / DNS / proxy | `python -m backend.firebase_sync --check`, try another network |
| `sign-in failed` | Anonymous sign-in disabled for the project | Firebase console → Authentication → Sign-in method → Anonymous |
| `pending: 1` never clears | upload rejected | read the error in the app's Cloud sync row; usually rules or a 403 |
| Installer/permission error on start | exe inside `Program Files` | move the folder to Desktop / `C:\AuraUI` |
| Brightness does not move | external monitor without DDC/CI, or a locked-down lab image | still records; brightness is an intervention, not data |
| `audio: volume keys` | `pycaw` not installed | `pip install pycaw`, restart the app |
| `audio: unavailable` | no default output device, or not Windows | fix the sound device in Windows settings |
| Volume moves but nothing gets quieter | app playing on a different output device than the default | set the intended device as Windows' default output |
| Session listed as `INCOMPLETE` | machine was force-quit mid-session | expected: no summary, never uploads; keep the local file as a note |
| SmartScreen on first launch | unsigned exe | More info → Run anyway (see `docs/TESTER_NOTES.md`) |

---

## 10. Day-of checklist

- [ ] Every station is a lab Windows machine, app folder is writable
- [ ] `lab_salt.txt` identical on every station
- [ ] `pycaw` installed on every station (`status` shows `Core Audio`)
- [ ] `status` shows `enabled`, a `station uid`, `pending: 0`
- [ ] Firestore rules published (`docs/FIREBASE_SETUP.md`)
- [ ] `check` on every station: named + `write test: write + delete confirmed`
- [ ] Consent version matches the current schema (`4`) and Participant Blinded Mode engages on recording
- [ ] Arm assignments written down (P01…P12 → intervention / control)
- [ ] Spotify allowlist not needed — audio is Windows system volume
- [ ] `prepare` run before each participant; `verify` + `reset` after
- [ ] Local `data/sessions` folders backed up (and CSVs exported via Lab Console or `research.export_dataset`) at the end of the day
