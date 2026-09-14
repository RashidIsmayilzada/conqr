# Deployment guide (Railway + Vercel)

ConQR has three moving pieces:

1. **watcher** — a small always-on Python process that polls your Google Form/Sheet and emails PDF tickets to new guests.
2. **scanner** — the Next.js web app used at the door to scan QR codes and check guests in.
3. **Google Apps Script webhook** — a script bound to your Google Sheet that lets the scanner write "Checked In" / "Checked In At" back into the sheet itself.

`watcher` needs to run continuously (Railway is a good fit). `scanner` is a normal web app (Vercel or Railway both work). The Apps Script webhook is hosted for free by Google — nothing to deploy on your end besides pasting the script in.

---

## 1. Google Sheet / Form setup

1. Your Google Form should collect at least: **Email**, **Ad Soyad** (full name), **Odenish** (payment), **Stol Nomresi** (table), **Ushag sayi** (baby/kid count). Other header names/languages work too — see `HEADER_ALIASES` in `src/core.py` if you need to add more.
2. Find the **Form Responses** tab (not a manually created "Sheet1"). Open it and copy the full URL, including the `gid=...` for that tab — this is your `BOOKINGS_URL`.
3. In the Sheet, go to **Extensions → Apps Script**, paste in `appsscript/checkin_webhook.gs`.
   - Set `SHARED_SECRET` to a random string (e.g. via `openssl rand -hex 16`).
   - Confirm `SHEET_NAME` matches your Form Responses tab name exactly.
   - Confirm `EMAIL_COLUMN_HEADER` / `NAME_COLUMN_HEADER` match your real column headers.
4. Click **Deploy → New deployment → Web app**. Execute as **Me**, access **Anyone with the link**. Copy the `/exec` URL — this is your `SHEET_CHECKIN_URL`. Use the same secret as `SHEET_CHECKIN_SECRET`.

---

## 2. Service: watcher (Railway)

- **Root directory:** repository root
- **Dockerfile:** `Dockerfile`
- **Start command:** use the Dockerfile default (`python src/conqr.py watch`)
- **Volume:** add a persistent volume mounted at `/app/database` so `guests.csv` (the sent-email log) survives restarts/redeploys.

The Dockerfile installs `reportlab` + `Pillow` for PDF ticket generation and bundles `assets/fonts/DejaVuSans*.ttf` so Azerbaijani characters (ə, ş, ö, ü, ğ, ı) render correctly in the ticket PDFs — no extra setup needed.

### Required environment variables

| Variable | Purpose |
| --- | --- |
| `BOOKINGS_URL` | Google Sheet "Form Responses" tab URL (with correct `gid`) |
| `SMTP_USER` | Gmail address used to send tickets |
| `SMTP_PASS` | Gmail App Password (not your normal password) |
| `SMTP_SERVER` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `QR_HOST` | Public URL of the `scanner` service (see wiring below) |

### Optional environment variables

| Variable | Purpose |
| --- | --- |
| `BOOKINGS_POLL_SECONDS` | How often `watch` mode re-checks the sheet (default 15s, min 5s) |
| `EVENT_NAME` | Shown on the ticket header and in the email subject |
| `TICKET_SUBJECT` | Email subject template, supports `{event}` |
| `TICKET_TEMPLATE` | Email body template, supports `{event}` and `\n` |
| `TICKET_LOGO_PATH` | Path to a PNG/JPG logo drawn on the ticket header |
| `CHECKIN_SYNC_URL` | POST target for pushing `guests.csv` to the scanner (see below) |
| `CHECKIN_SYNC_SECRET` | Shared secret for `CHECKIN_SYNC_URL` |
| `SHEET_CHECKIN_URL` | Apps Script `/exec` URL (see step 1.4 above) |
| `SHEET_CHECKIN_SECRET` | Shared secret matching `SHARED_SECRET` in the Apps Script |

---

## 3. Service: scanner (Vercel or Railway)

- **Root directory:** `web`
- Vercel: standard Next.js deploy, no Dockerfile needed.
- Railway: **Dockerfile:** `web/Dockerfile`, public port routed to `PORT`.

### Required environment variables

| Variable | Purpose |
| --- | --- |
| `CHECKIN_PIN` | PIN guests/staff enter to unlock the scanner UI |
| `CHECKIN_SYNC_SECRET` | Must match the watcher's `CHECKIN_SYNC_SECRET` |

### Optional environment variables

| Variable | Purpose |
| --- | --- |
| `KV_REST_API_URL` / `KV_REST_API_TOKEN` | Vercel KV, so scanned check-ins survive redeploys/cold starts |
| `SHEET_CHECKIN_URL` | Same Apps Script `/exec` URL as the watcher, so scans from the phone also update the Google Sheet directly |
| `SHEET_CHECKIN_SECRET` | Must match `SHARED_SECRET` in the Apps Script |

---

## 4. Wiring them together

1. Deploy `scanner` first and copy its public URL (e.g. `https://scanner-production.up.railway.app` or `https://your-app.vercel.app`).
2. Set `QR_HOST` on `watcher` to that public URL — this is what gets embedded inside every ticket's QR code.
3. Set `CHECKIN_SYNC_URL` on `watcher` to `<scanner-url>/api/sync`, and use the same `CHECKIN_SYNC_SECRET` on both services.
4. Set `SHEET_CHECKIN_URL` + `SHEET_CHECKIN_SECRET` identically on **both** `watcher` and `scanner`, so a check-in from either side reflects in the Google Sheet.
5. Add a persistent volume to `watcher` at `/app/database` so `guests.csv` survives restarts.

---

## Notes

- `watcher` only emails rows that are not already recorded in `/app/database/guests.csv` — safe to re-run or restart without duplicate sends.
- Every successful check-in (from the `scanner` web UI) also fires a best-effort webhook call to the Google Apps Script, writing "Checked In" / "Checked In At" straight into your Sheet. If that call fails (network hiccup, wrong secret, row not found), the local check-in still succeeds — it just logs a warning.
- If you want scanner data to survive Vercel cold starts/redeploys independently of the Sheet webhook, add Vercel KV credentials.
- To test the full pipeline locally before deploying, use `scripts/dry_run_sheet.py` (shows what would be emailed without sending) and `scripts/test_send_dummy.py` (sends real test emails to a throwaway address without touching your real `database/guests.csv`).
