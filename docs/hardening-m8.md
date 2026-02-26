# Milestone 8 — Hardening Summary

> **Milestone:** M8 — Hardening, QA, Polish, and Operational Readiness  
> **Date:** 2026-02  
> **Deployment target:** notes.defecttracker.uk (Plesk, Passenger WSGI)

---

## Changes Delivered

### 1. HTTP Security Headers

All responses (pages, API, static files) now include the following headers, added via a global `after_request` hook in the Flask app factory:

| Header | Value |
|---|---|
| `X-Frame-Options` | `DENY` |
| `X-Content-Type-Options` | `nosniff` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=(), payment=()` |
| `Content-Security-Policy` | `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; worker-src 'self';` |

**What this prevents:**
- `X-Frame-Options: DENY` — clickjacking (embedding the app in a malicious frame)
- `X-Content-Type-Options: nosniff` — MIME-type sniffing attacks
- `Referrer-Policy` — leaking the full URL to third parties in referrer headers
- `Permissions-Policy` — unwanted browser API access (camera, mic, etc.)
- `CSP` — cross-site scripting (XSS) by restricting where scripts can load from

**Note on `style-src 'unsafe-inline'`:** The dashboard and settings pages use minor inline styles (`style="display:none"` etc.). A future improvement is to extract these to class-based CSS and remove `'unsafe-inline'`.

---

### 2. Input Length Validation

API endpoints `POST /api/notes` and `PUT /api/notes/<id>` now enforce:

| Field | Max length | HTTP response on violation |
|---|---|---|
| `title` | 500 characters | `400 Bad Request` |
| `body` | 100 000 characters | `400 Bad Request` |

This prevents excessively large payloads from reaching the database and exhausting server resources.

---

### 3. Error Handling Improvements

- **Global 500 handler** — uncaught exceptions are logged via `app.logger.exception()` and return `{"error": "Internal server error"}` for API routes (`/api/*`) or the `error.html` template for browser routes. This prevents raw tracebacks leaking to users.
- **413 handler** — requests exceeding `MAX_CONTENT_LENGTH` (12 MB) now return a consistent JSON `{"error": "File too large (max 10 MB)"}` for API routes.
- **Blueprint-level 500 handler** added to the `main` blueprint for belt-and-suspenders coverage.
- New `templates/error.html` — simple, styled error page for non-API 500 errors.

---

### 4. Settings Page

A new `/settings` page and associated API endpoint provide:

| Feature | Details |
|---|---|
| **Account info** | Displays current username |
| **Change password** | `POST /api/settings/password` — validates current password, enforces 8–128 char limit, requires confirmation match |
| **Dark mode toggle** | Client-side preference persisted in `localStorage` (no server round-trip) |

The settings page is linked from the sidebar footer (⚙️ icon).

---

### 5. Authentication & Session (existing hardening — confirmed)

These were already implemented in earlier milestones and confirmed still in place:

- Passwords stored as Werkzeug `pbkdf2:sha256` hashes — never plaintext.
- `SESSION_COOKIE_HTTPONLY = True` — JavaScript cannot access session cookies.
- `SESSION_COOKIE_SAMESITE = 'Lax'` — CSRF protection for same-site navigation.
- `SESSION_COOKIE_SECURE` — set via `SESSION_COOKIE_SECURE=true` in `.env` for production HTTPS.
- Open-redirect protection in login `next` parameter (must start with `/`, not `//`).
- Deliberate vague login error ("Invalid username or password") — no username enumeration.
- Minimum password length enforced at user creation (8 chars).

---

### 6. File Upload Security (existing hardening — confirmed)

- MIME type validated against allowlist: `image/jpeg`, `image/png`, `image/gif`, `image/webp`.
- Extension-to-MIME cross-check for double validation.
- UUID-based filenames — user-supplied filenames never used on the filesystem.
- `MAX_CONTENT_LENGTH = 12 MB` enforced server-side (Flask).
- Images resized to max 1920 px and re-encoded (Pillow) — strips EXIF metadata.
- Media served via `/media/<filename>` with ownership check — no direct filesystem access.

---

### 7. SQL Injection (existing hardening — confirmed)

All database queries use SQLite parameterised statements (`?` placeholders). No string-interpolated SQL was found in `routes.py`, `database.py`, `media.py`, or `pdf.py`.

---

## Known Limitations / Future Improvements

| Item | Priority | Notes |
|---|---|---|
| Rate-limiting on `/login` | High | Plesk/Apache `.htaccess` `mod_ratelimit` or `mod_evasive` can be used without code changes |
| Remove `'unsafe-inline'` from CSP `style-src` | Medium | Requires CSS refactor to eliminate inline `style=""` attributes |
| HSTS header | High | Best applied at Plesk/Apache level; do not add in Flask if behind a proxy that strips headers |
| Password reset flow | Medium | Currently only possible via SSH `flask create-user` |
| Account lockout after N failed logins | Medium | Requires a `login_attempts` table or Redis; not currently implemented |
| Two-factor authentication | Low | Out of scope for personal single-user deployment |
