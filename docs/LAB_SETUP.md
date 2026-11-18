# Running Aura UI in a lab (multi-station setup)

For a study where 10–12 participants each sit at a station for 20–30 minutes.
One section per thing that actually goes wrong on the day.

> **Windows only.** Brightness, colour temperature, Focus Assist and system
> volume all use Windows APIs. The sign-up form currently offers "macOS / Linux"
> — anyone who picks that cannot run this build. Filter them out or run them on
> a lab Windows machine.

---

## 1. The three constraints to decide around first

| Constraint | Reality | What to do |
|---|---|---|
| **Station OS** | Windows 10/11, 64-bit | Everyone on lab Windows machines, or drop non-Windows sign-ups |
| **Spotify accounts** | A Development-Mode Spotify app allows **5 users**, and the owner needs **Premium**. User 6 gets HTTP 403 | Either accept "system audio" for most participants (see §5), register **3 apps** of 5 users each, or apply for Extended Quota — approval is not instant |
| **Database** | Firestore, one anonymous identity per station | Nothing to do per participant — but every station must reach the internet |

**Spotify is optional.** The Music panel falls back to the **Windows master
volume**, so a participant who never links an account still experiences the
"music gets quieter when you're stressed" intervention. Auto-lower drives
whatever audio is playing — Spotify, YouTube, a local player.

---

## 2. What each station needs

- `AuraUI.exe` (or a source checkout) in a **writable folder** — Desktop or
  `C:\AuraUI`. **Never `C:\Program Files`**: the app keeps its data next to the
  exe and cannot write there.
- **`lab_salt.txt`** in the same folder (see §3) — without it the same
  participant code becomes a *different* pseudonym on every machine.
- Internet.
- Optional but recommended: `pycaw` for exact volume control
  (`pip install pycaw`). Without it the app uses the volume media keys, which is
  approximate but works.

Copy the whole folder to each station rather than re-downloading; that is how
`lab_salt.txt` and the identity stay consistent.

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
python tools/lab_setup.py status
```

You want to see:

```
  lab salt   : shared (.../lab_salt.txt)
  firebase   : aura-ui-hci / aura_sessions | enabled
  station uid: <some id>            <- proves anonymous sign-in works
  pending    : 0 session(s) waiting to upload
  spotify    : configured | not linked
  audio      : system volume via Core Audio     (or "volume keys")
```

`NOT SET` salt, `sign-in failed`, or `audio: unavailable` are the three things to
fix before participants arrive.

> **Building the exe yourself?** The volume code imports `pycaw` lazily, so give
> PyInstaller the hint, otherwise the packaged build silently falls back to
> media keys:
> ```bash
> python -m PyInstaller --onefile --noconsole --name "AuraUI" \
>        --add-data "aura_defaults.json;." \
>        --hidden-import pycaw --hidden-import comtypes run.py
> ```

---

## 4. Before each participant (30 seconds)

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

1. Launches Aura UI.
2. Ticks **Record session** when the task starts (the button shows `● Rec 00:00`).
3. Optionally clicks **Connect Spotify** and signs in with their own account.
4. Works for 20–30 minutes.
5. Journal → 0–10 ratings → **Save entry** (this finalises and uploads).

---

## 5. Spotify: what actually happens

**Linking** — the participant clicks **Connect Spotify**; their browser opens
Spotify's own login; they approve. PKCE means no client secret exists anywhere,
and the token is cached per machine. Nothing authenticates until that button is
pressed.

**Limits** — with a Development-Mode app only the 5 allowlisted Spotify accounts
in *Dashboard → Settings → User Management* can link. The 6th gets:

> *This Spotify account must be added as a test user*

Options, in order of effort:

1. **Accept the fallback** (recommended for a class study): ask each participant
   to play music on any device. The app controls **Windows master volume**, so
   the intervention still lands. Set `pycaw` up and it is exact.
2. **Register more apps** — 5 accounts per app. Three apps cover 15 people. Put
   the matching `spotify_client_id` in that station group's `secrets.json`
   (it overrides the built-in id).
3. **Extended Quota Mode** — proper fix, but it is an application + review.

**Playback controls** need an active Spotify device (phone or desktop app open).
If the panel says *Nothing playing*, nothing is broken — there is just no active
device.

---

## 6. After each participant

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

## 7. Where the data goes

Each finished session becomes **one Firestore document** in `aura_sessions`:

- id = `<pseudonym>_<session_id>` — unique per session, no collisions between
  stations
- pseudonym from the **lab salt** + participant code
- numeric telemetry only (≤ 800 sampled ticks, plus summary, ratings, journal text)
- `uid` = the station's anonymous Firebase identity (this is what the security
  rules check)
- `chain_ok` — false if the local log was damaged (e.g. the machine was killed
  mid-session); such a document is still uploaded but flagged

Doc ids look like `e73582e4a42d3d2a_20261116-165231-6d9b6f`. One participant on
two stations produces two pseudonym dirs only if the salt differs — with
`lab_salt.txt` it produces the same pseudonym.

**Local copies** stay in `data/sessions/<pseudonym>/` on the station, plus
`journal.json` and `settings.json`. Keep the folders until the study is written
up; they are your backup if the network died.

**Withdrawal** — Privacy → *Withdraw + delete* deletes the local files *and* this
station's uploaded documents for that pseudonym. On a multi-station lab, run it
from each station the participant used.

---

## 8. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `[warn] no lab_salt.txt` | station missing the shared salt | copy `lab_salt.txt` into the folder, re-run `prepare` |
| `sign-in failed` | no internet, wrong `api_key`, or Anonymous sign-in disabled | `python -m backend.firebase_sync --check` |
| `pending: 1` never clears | upload rejected | read the error in the app's Cloud sync row; usually rules not published or a 403 |
| Installer/permission error on start | exe inside `Program Files` | move the folder to Desktop / `C:\AuraUI` |
| Brightness does not move | external monitor without DDC/CI, or a locked-down lab image | still records; brightness is an intervention, not data |
| Panel says *Account not allowed* | not in the Spotify allowlist (5-user cap) | use system audio, or add them to a second app |
| `audio: unavailable` | no `pycaw`, not Windows | `pip install pycaw`, restart |
| Session listed as `INCOMPLETE` | machine was force-quit mid-session | expected: no summary, never uploads; keep the local file as a note |
| SmartScreen on first launch | unsigned exe | More info → Run anyway (see `docs/TESTER_NOTES.md`) |

---

## 9. Day-of checklist

- [ ] Windows machines only; non-Windows sign-ups moved to a lab station
- [ ] `lab_salt.txt` identical on every station
- [ ] `status` shows `enabled`, a `station uid`, `pending: 0`, `audio` available
- [ ] Firestore rules published (`docs/FIREBASE_SETUP.md`)
- [ ] Consent text version matches the one in the app (3.0)
- [ ] Arm assignments written down (P01…P12 → intervention / control)
- [ ] Spot plan: allowlisted accounts listed, or "everyone uses system audio"
- [ ] `prepare` run before each participant; `verify` + `reset` after
- [ ] Local `data/sessions` folders backed up at the end of the day
