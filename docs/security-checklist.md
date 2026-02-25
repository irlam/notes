# Security Checklist — Notes PWA

> **Deployment target:** notes.defecttracker.uk (Plesk, Passenger WSGI)  
> This checklist covers v1 (single-user, no auth) and notes future auth requirements.

---

## 1. Transport Security

- [ ] HTTPS enforced for the domain (Plesk Let's Encrypt or existing certificate).
- [ ] HTTP → HTTPS redirect configured in Plesk or `.htaccess`.
- [ ] HSTS header set (`Strict-Transport-Security: max-age=31536000; includeSubDomains`).
- [ ] TLS 1.2+ enforced; TLS 1.0/1.1 disabled in Plesk SSL/TLS settings.
- [ ] Certificate auto-renewal configured (Let's Encrypt).

---

## 2. Flask / Application Security

- [ ] `SECRET_KEY` is a cryptographically random string ≥ 32 hex characters (never the default).
- [ ] `FLASK_ENV=production` in `.env` (disables debug mode and the Werkzeug debugger).
- [ ] Debug mode confirmed off (`app.debug is False`) in production.
- [ ] Werkzeug debugger PIN not exposed.
- [ ] No sensitive data logged to error logs (e.g. full request bodies, tokens).

---

## 3. Input Validation & Output Encoding

- [ ] All API inputs validated server-side (type checks, length limits).
- [ ] Note `title` and `body` are stored as raw text; no server-side HTML rendering.
- [ ] If rich-text (HTML) body is added (M3), a server-side HTML sanitiser (e.g. `bleach`) is applied before storage and before rendering.
- [ ] JSON responses set `Content-Type: application/json` (Flask default).
- [ ] No `eval()` or `innerHTML` with unsanitised server data in the frontend JS.

---

## 4. SQL Injection

- [ ] All database queries use parameterised statements (SQLite `?` placeholders).
- [ ] No string-interpolated SQL anywhere in `database.py` or `routes.py`.

---

## 5. CSRF (applies from M5+ auth milestone)

- [ ] CSRF token generated per session and validated on all state-changing requests (POST, PUT, DELETE).
- [ ] `SameSite=Lax` or `SameSite=Strict` set on session cookies.
- [ ] CSRF exemption documented and justified for any API endpoints that require it.

---

## 6. Authentication & Session (M5+)

- [ ] Passwords stored as bcrypt hashes (cost factor ≥ 12).
- [ ] No password stored in plaintext, logs, or error messages.
- [ ] Session cookie: `HttpOnly`, `Secure`, `SameSite=Lax`.
- [ ] Session expiry: 30 days of inactivity.
- [ ] Brute-force protection: rate-limit on `/login` (e.g. Flask-Limiter or Nginx rate-limit).
- [ ] Password reset tokens are single-use and expire after 1 hour.
- [ ] Password reset emails do not confirm whether an email address is registered (prevents enumeration).

---

## 7. File Upload Security (M3 — image attachments)

- [ ] File type validated by MIME type (not just extension) using `python-magic` or equivalent.
- [ ] Allowed types whitelist: `image/jpeg`, `image/png`, `image/gif`, `image/webp`.
- [ ] Maximum file size enforced server-side (e.g. 10 MB per image).
- [ ] Files stored outside the web root or served via a dedicated endpoint with `Content-Disposition: attachment` to prevent MIME sniffing.
- [ ] Uploaded filenames sanitised (UUIDs or hashed names; never user-supplied filenames).
- [ ] `X-Content-Type-Options: nosniff` header set on file-serving responses.

---

## 8. HTTP Security Headers

- [ ] `Content-Security-Policy` (CSP) defined and tested.
  - Baseline: `default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self';`
  - Adjusted when third-party CDN resources are added.
- [ ] `X-Frame-Options: DENY` (or `SAMEORIGIN`) to prevent clickjacking.
- [ ] `X-Content-Type-Options: nosniff`.
- [ ] `Referrer-Policy: strict-origin-when-cross-origin`.
- [ ] `Permissions-Policy` restricts unneeded browser features (e.g. camera, microphone unless explicitly needed).

---

## 9. PWA / Service Worker Security

- [ ] Service worker is served over HTTPS.
- [ ] Service worker scope is limited to `/` (no over-broad scope).
- [ ] Cached resources are version-bumped on each deployment to prevent stale content.
- [ ] Sensitive API responses are not cached by the service worker (API calls bypass cache).
- [ ] IndexedDB data (offline queue) contains only the note content, not auth tokens.

---

## 10. Plesk / Server Security

- [ ] `.env` file permissions set to `640` (owner read/write; group read; no world access).
- [ ] `notes.db` SQLite file stored outside the web root or protected via Plesk directory protection.
- [ ] Passenger WSGI application user (`psacln`) has the minimum required filesystem permissions.
- [ ] Plesk Firewall rules reviewed; only ports 80 and 443 exposed publicly.
- [ ] SSH access restricted to key-based authentication; password auth disabled.
- [ ] Plesk admin panel access restricted by IP allowlist if possible.
- [ ] Server and Plesk packages kept up to date.

---

## 11. Dependency Security

- [ ] `requirements.txt` pinned to specific versions.
- [ ] Dependabot or manual periodic review of dependencies for CVEs.
- [ ] No development dependencies included in the production `requirements.txt`.

---

## 12. Pre-Deployment Sign-Off

| Check | Verified by | Date |
|---|---|---|
| HTTPS active and certificate valid | | |
| `SECRET_KEY` changed from default | | |
| `FLASK_ENV=production` confirmed | | |
| `.env` permissions set to 640 | | |
| CSP header tested (no console errors) | | |
| SQL injection spot-check passed | | |
| No sensitive data in error logs | | |
