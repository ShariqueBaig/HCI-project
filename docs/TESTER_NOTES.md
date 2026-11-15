# Aura UI — Tester notes

Two minutes of setup, then just work normally. No installation, no Python, no config files.

---

## 1. Run it

1. Download `AuraUI.exe` anywhere you like (Desktop, Documents — **not** `Program Files`,
   which is read-only and stops it saving your session).
2. Double-click it. The first start takes a few seconds while the exe unpacks itself.

> **"Windows protected your PC" (SmartScreen).**
> This is expected: the app is not code-signed (that needs a paid certificate). Click
> **More info → Run anyway**. If your antivirus flags it, that is also typical of
> single-file Python builds — the full source is in this repo.

Windows 10/11, 64-bit.

## 2. Give consent & calibrate (nothing is recorded without consent)

1. In the app, click **Privacy** (small link under the brightness row).
2. Type the **participant code** your researcher gave you.
3. Read the text and click **Save consent**.
4. *(Optional)* Click **Calibrate** to open the 30-second calibration box, type the sample
   paragraph at your normal relaxed pace, and let it save your baseline rhythm.

Until you save consent, ticking **Record session** just re-opens the Privacy dialog — by design.

## 3. Record a session

- *(If your researcher assigned you a study condition, check that the button next to Calibrate
  shows **Mode: Active (B)** or **Mode: Control (A)** as instructed.)*
- Tick **Record session**, then work normally. A live **`● Rec MM:SS`** timer appears on the
  checkbox and gauge while recording.
- When you finish: **uncheck `Record session`** (or click **Journal**). The **Journal** window
  opens automatically → set **Perceived stress (0–10)** and **Mood (0–10)** → click
  **Save entry**. That finalizes the session and attaches your ratings (plus any note) to it.
- The **Cloud sync** row tells you where it stands:
  - green `everything uploaded` — it reached the research database
  - amber `1 queued for upload` — waiting, will send shortly
  - red with an error — usually offline; it retries every 5 minutes
- A note saved *without* ticking Record is still kept, as a "journal-only" entry.

## 4. Link Spotify (optional)

1. In the **Music** panel, click **Connect Spotify**.
2. Your browser opens Spotify's login page — sign in with **your own** account and click
   **Agree**. Nothing opens until you press that button.
3. Come back to the app; the panel should say *Connected as <your name>*.

If instead you see *"This Spotify account must be added as a test user"* (HTTP 403), the app
owner has to add your Spotify email in the Spotify Developer Dashboard → your app →
**Settings → Users Management**. Development Mode allows **5 testers**, and the owner's
account needs **Spotify Premium**. Playback controls also need an active Spotify device
(the phone or desktop app open).

## 5. What is and isn't recorded

- **Recorded:** typing speed, timing variability, backspace rate, mouse movement, the stress
  score/tier over time, your 0–10 ratings, and any note you write.
- **Never recorded:** the characters you type, key codes, window titles, app names.
- Your data is stored under a pseudonymous code, not your name.
- Please don't write anything in the journal you wouldn't want in the research dataset.
- **Privacy → Withdraw + delete** removes your local files *and* the documents this install
  uploaded.

## Where it keeps your data

Everything sits beside `AuraUI.exe` in a `data/` folder, plus `settings.json` and
`journal.json` (or in `%APPDATA%\AuraUI` if that folder isn't writable).
Deleting the whole folder resets the app completely.
