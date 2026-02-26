# Milestone 10 — Direct Email PDF + Batch Export

> **Status:** Stubs in place. Full implementation planned.  
> **Deployment target:** notes.defecttracker.uk  
> **Hosting:** Plesk (Passenger WSGI, Python) — no Docker

---

## Summary

M10 adds two bulk-output features:

1. **Email PDF** — the user can click a button in the editor toolbar to have
   the current note's PDF emailed directly to them (or a specified address).
2. **Batch Export** — the user can select multiple notes and download them as a
   ZIP archive (one PDF per note) or as a combined multi-note PDF.

Both features are currently **feature-flagged and not implemented**.
Stub endpoints that return `403` (flag off) or `501` (flag on, not yet built)
are already in place in `app/email_export.py`.

---

## Task Breakdown

### 1. Email PDF

#### Backend tasks

| # | Task | Notes |
|---|---|---|
| EP-1 | SMTP transport layer (`app/email.py`) | Use Python `smtplib` + `email.mime`; config from env vars |
| EP-2 | Rate limiting per user | e.g. max 10 email sends per hour; use in-memory counter or DB table |
| EP-3 | Note ownership check | Verify `note.user_id == session['user_id']` before sending |
| EP-4 | Generate PDF attachment | Reuse existing `app/pdf.py` `generate_pdf()` logic |
| EP-5 | Compose and send email | To: user's address (stored in `users` table — add `email` column) |
| EP-6 | Add `email` column to `users` table (migration `006_add_user_email.sql`) | Nullable; no change required for existing users |
| EP-7 | Update `flask create-user` CLI to accept optional `--email` argument | |
| EP-8 | Settings page: "Email address" field for users to store/update their address | |
| EP-9 | Error handling: SMTP failure → JSON `{"error": "Failed to send email"}` 500 | |
| EP-10 | Tests (mock SMTP): ownership, rate-limit, success, failure | |

#### Frontend tasks

| # | Task | Notes |
|---|---|---|
| EP-F1 | Enable `btn-email-pdf` button when `ENABLE_EMAIL_EXPORT=true` | Currently disabled stub |
| EP-F2 | On click: POST `/api/notes/<id>/email-pdf`; show "Sending…" state | |
| EP-F3 | On success (200): show "✉️ PDF sent to your email" toast | |
| EP-F4 | On failure: show error toast with message from API response | |

---

### 2. Batch Export

#### Backend tasks

| # | Task | Notes |
|---|---|---|
| BE-1 | `POST /api/batch-export` — accept `{"note_ids": [...], "format": "zip|pdf"}` | |
| BE-2 | Input validation: max 50 note IDs; all must be owned by current user | Return 400 or 404 on violation |
| BE-3 | Generate per-note PDFs using existing `app/pdf.py` | Stream or collect into BytesIO |
| BE-4 | ZIP format: create in-memory `zipfile.ZipFile`; one `<title>.pdf` per note | |
| BE-5 | Combined PDF format: merge pages using `reportlab`'s `PageBreak` or `PyPDF2` | |
| BE-6 | Stream response as `application/zip` or `application/pdf` with `Content-Disposition: attachment` | |
| BE-7 | Tests: ownership, size cap, ZIP content check, combined PDF content check | |

#### Frontend tasks

| # | Task | Notes |
|---|---|---|
| BE-F1 | "Select notes" mode in sidebar (checkbox on each note item) | |
| BE-F2 | "Batch Export" toolbar button appears when ≥1 note is selected | |
| BE-F3 | Format picker: "ZIP (one PDF each)" vs "Combined PDF" | |
| BE-F4 | POST to `/api/batch-export`; trigger download via `<a download>` blob URL | |
| BE-F5 | Clear selection after download | |

---

## Acceptance Criteria

### Email PDF
- [ ] Authenticated user can email a PDF of any of their own notes.
- [ ] Email is sent to the address stored in the user's profile.
- [ ] Email contains the note title as subject and the PDF as an attachment.
- [ ] Rate limit: at most 10 emails per user per hour; excess returns `429 Too Many Requests`.
- [ ] Attempting to email another user's note returns `404 Not Found`.
- [ ] Unauthenticated request returns `401 Unauthorized`.
- [ ] SMTP errors return a safe `500` response; credentials are never leaked in the response body.
- [ ] `ENABLE_EMAIL_EXPORT=false` (default) disables the endpoint entirely (returns `403`).
- [ ] All acceptance tests pass with mocked SMTP (no real emails sent in test suite).

### Batch Export
- [ ] Authenticated user can export 1–50 of their own notes in one request.
- [ ] ZIP format: archive contains one `<sanitised-title>.pdf` per note.
- [ ] Combined PDF format: all notes concatenated into a single PDF, separated by page breaks.
- [ ] Requesting notes that don't belong to the user returns `404`.
- [ ] Requesting > 50 notes returns `400 Bad Request`.
- [ ] Empty `note_ids` list returns `400 Bad Request`.
- [ ] Download response has correct `Content-Disposition: attachment` header.

---

## Security Considerations

| Concern | Mitigation |
|---|---|
| Open email relay | `SMTP_FROM` is fixed in env; recipients restricted to the authenticated user's stored address |
| SMTP credential exposure | Credentials only in `.env` (excluded from git); never returned in API responses or logs |
| Phishing via subject/body | Subject line is server-generated from the note title (HTML-stripped); body is a PDF binary |
| Batch DoS | Hard cap of 50 notes per request; rate limiting on the endpoint |
| Path traversal in ZIP | Filenames sanitised: alphanumeric + hyphen/underscore only, max 100 chars |
| SSRF via SMTP_HOST | `SMTP_HOST` is a static env var; not user-controlled per request |
| Note ownership bypass | All note IDs verified against `user_id = session['user_id']` before processing |

---

## UI Flow

### Email PDF

```
User opens a note
→ clicks ✉️ "Email PDF" toolbar button
→ button shows "Sending…" (spinner)
→ POST /api/notes/<id>/email-pdf
→ on success: toast "✉️ PDF sent to your.email@example.com"
→ on failure: toast "❌ Could not send email: <reason>"
```

### Batch Export

```
User clicks "Select" mode in sidebar
→ checks 1–50 notes
→ clicks "📦 Export selected" button (appears in header)
→ format picker dialog: "ZIP" or "Combined PDF"
→ POST /api/batch-export  {"note_ids": [...], "format": "zip"}
→ browser triggers file download
→ selection cleared automatically
```

---

## Environment Variables (add to `.env.example`)

```
ENABLE_EMAIL_EXPORT=false   # Set true once implementation is complete
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=notes@example.com
SMTP_PASS=<secret-never-committed>
SMTP_FROM=Notes App <notes@example.com>
```

---

## New Database Migration Required

`migrations/006_add_user_email.sql`:

```sql
ALTER TABLE users ADD COLUMN email TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users (email);
```

---

## Dependencies (if needed)

No new third-party dependencies are required:
- `smtplib` (stdlib) — SMTP sending
- `email.mime` (stdlib) — email composition
- `zipfile` (stdlib) — ZIP creation
- `reportlab` (already installed) — PDF generation

---

## Issue Templates

See:
- `.github/ISSUE_TEMPLATE/milestone-10-email-pdf.md`
- `.github/ISSUE_TEMPLATE/milestone-10-batch-export.md`
