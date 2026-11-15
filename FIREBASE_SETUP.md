# Firebase setup — step by step

Goal: **you configure Firebase once; every copy of the app then uploads on its own.**
End users install the app and do nothing else — no login screen, no keys to paste.

Total time: ~10 minutes. Cost: ₹0 / $0 (Firestore Spark free tier: 20,000 document
writes and 50,000 reads per day; one recorded session = **one** write).

---

## Step 1 — Create the project

1. Open <https://console.firebase.google.com> and sign in with a Google account.
2. **Add project** → name it (e.g. `aura-ui-hci`) → **Continue**.
3. Google Analytics: **not required** — disable it → **Create project** → wait → **Continue**.

## Step 2 — Create the database

1. Left sidebar → **Build → Firestore Database** → **Create database**.
2. Location: pick the closest region (e.g. `asia-south1`). *This cannot be changed later.*
3. Mode: **Production mode** (rules start closed; you paste the real rules in Step 5).

## Step 3 — Enable anonymous sign-in

This is what lets each install get its own identity without a login screen.

1. Sidebar → **Build → Authentication** → **Get started**.
2. **Sign-in method** tab → click **Anonymous** → toggle **Enable** → **Save**.

## Step 4 — Copy the two config values

1. Click the ⚙ gear (top-left) → **Project settings**.
2. **General** tab → **Project ID** (e.g. `aura-ui-hci`) — copy it.
3. Scroll to **Your apps**. If there is no app, click the **`</>`** (Web) icon → give it a
   nickname → **Register app** (you do *not* need the SDK snippet).
4. Copy the **Web API key** (`AIza…`).

> The Web API key is **public by design** — Google ships it in every web client. It
> identifies the project, not a user. It is safe to put in the app package. Access is
> controlled by the security rules in Step 5.

## Step 5 — Create the config file

In the project folder:

```bash
cp firebase_config.example.json firebase_config.json
```

Edit `firebase_config.json`:

```json
{
  "project_id": "aura-ui-hci",
  "api_key": "AIza...your-web-api-key...",
  "collection": "aura_sessions"
}
```

`firebase_config.json` is git-ignored. To ship the app, place this file **next to the
executable** (a frozen build reads it from the `.exe` folder) or keep it beside `run.py`.

## Step 6 — Publish the security rules

Firestore → **Rules** tab → replace everything with:

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /aura_sessions/{doc} {
      // Any signed-in install may create a document, but only one that carries
      // its own uid. Read and edit stay closed.
      allow create: if request.auth != null
                    && request.resource.data.uid == request.auth.uid;
      // Consent withdrawal erases this install's own documents; nothing else.
      allow delete: if request.auth != null
                    && resource.data.uid == request.auth.uid;
      allow read, update: if false;
    }
  }
}
```

Click **Publish**. Wait ~1 minute for the rules to propagate.

Why this is safe: without `request.auth`, writes are rejected; the `uid` check means one
install cannot forge another's uploads; denying `read`/`update` keeps the corpus
unreadable and unmodifiable from any client; and `delete` is limited to documents
the caller's own uid uploaded, which is what makes consent withdrawal work. As the
project owner you read the data in the Firebase console, which bypasses rules.

## Step 7 — Verify the connection

```bash
python -m backend.firebase_sync --check
```

Expected:

```
config     : ...\firebase_config.json
project    : aura-ui-hci
collection : aura_sessions
enabled    : True
pending    : 0
uid        : xK3pQ9...            <- a uid was issued to this install
status     : connected
```

If you see `enabled : False`, the config file is missing or still has `YOUR_...`
placeholders. If sign-in fails, see *Troubleshooting*.

## Step 8 — Send a real session

```bash
python run.py                     # Privacy -> participant code -> Save consent
# tick "Record session", work, then Journal -> Save entry to close the session
python -m backend.firebase_sync --push
```

Expected: `push : {'uploaded': 1, 'failed': 0, 'errors': []}`.

Open **Firestore Database → Data → `aura_sessions`** — you should see one document
named `{pseudonym}_{session_id}` containing the summary fields, sampling metadata
(`tick_sampled`, `tick_stride`), and a `tick_data` array of per-tick rows (sessions longer
than 800 ticks are automatically downsampled for cloud upload while preserving start, peak,
and end ticks so documents stay safely below Firestore's 1 MiB limit; local `.jsonl` files
keep every 3 Hz tick).

After that the app syncs by itself: on launch, after each session closes, and every
5 minutes for anything queued. A file is only marked `.synced` after a confirmed write,
so nothing is lost while offline.

## Step 9 — Distribute

Bundle `firebase_config.json` with the app. On first run each install silently:

1. calls `accounts:signUp` for anonymous auth → receives its own `uid`;
2. caches the refresh token in `data/firebase_identity.json`;
3. uploads its sessions to `aura_sessions`.

No user-facing step exists, and two installs never collide: different uid and different
pseudonym produce different document IDs.

## Step 10 — Read the data

- **Console:** Firestore → Data. Fine for spot checks.
- **Bulk export:** install the Admin SDK on your own machine and export, or
  `gcloud firestore export gs://...`. The app's REST writes are append-only on purpose.
- **Local CSV** (no Firebase needed): `backend.research.export_dataset('exports')`.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `enabled : False` | `firebase_config.json` missing, or placeholders | Do Steps 4–5 |
| `sign-in failed: HTTP 400 API_KEY_INVALID` | Wrong key | Re-copy **Web API key** |
| `ADMIN_ONLY_OPERATION` / `OPERATION_NOT_ALLOWED` | Anonymous auth not enabled | Step 3 |
| `HTTP 404 NOT_FOUND` | Wrong `project_id`, or Firestore not created | Steps 1–2 |
| `HTTP 403 PERMISSION_DENIED` on write | Rules not published / not yet propagated | Step 6, wait 1 min |
| `PERMISSION_DENIED` with `request.auth == null` | Anonymous sign-in blocked | Step 3, check the key is unrestricted |
| `HTTP 429 RESOURCE_EXHAUSTED` | Daily free quota hit | Wait for reset (midnight PT) |
| `push` reports `failed: 1` but `pending` unchanged | Network/offline | Retried automatically every 5 min |
| Key restrictions break auth | You restricted the key to HTTP referrers | Restrict by **API** instead: allow *Identity Toolkit API* + *Cloud Firestore API* |

## Privacy notes specific to Firebase

- Uploaded: pseudonym (salted hash), numeric typing/mouse aggregates, score/tier,
  timings, self-report, the participant's journal note and Aura's reflection (consent
  v3), and the install's anonymous `uid`. **Never**: characters typed, key codes, window
  titles, app names, or the salt.
- The journal note is free text, so it is the one field that can contain whatever the
  participant chose to write. It is covered by the consent text shown in the app; if a
  study must exclude free text, drop `journal_note`/`journal_reflection` in
  `FirebaseSync.build_document`.
- Sessions upload only if the user gave consent in the app; the collector refuses to
  record otherwise.
- Withdrawing consent erases **both** copies: the app first deletes the Firestore
  documents it uploaded for that participant (allowed by the `delete` rule above; each
  attempt is reported in the dialog), then purges the local session files.
  Limitation: erasure covers documents **this install** uploaded. If a participant's code
  was used on another machine, that machine's documents carry a different `uid` and must
  be erased there (or from the console).
- Because reads are denied by rules, neither the app nor another user can read the
  corpus; only the project owner can.
