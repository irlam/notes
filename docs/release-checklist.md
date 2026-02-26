# Release Checklist — Notes v1 (First Production Use)

> **Deployment target:** notes.defecttracker.uk  
> **Hosting:** Plesk (Passenger WSGI, Python) — no Docker  
> Complete all items below before going live. Mark each ✅ Pass or ❌ Fail (with notes).

---

## 1. Pre-Deployment — Local / Staging Verification

| # | Check | Status | Notes |
|---|---|---|---|
| P-01 | All automated tests pass: `python -m pytest tests/ -v` | | |
| P-02 | App starts locally with `bash run.sh` and loads at http://localhost:5000 | | |
| P-03 | Can create, edit, and delete a note without errors | | |
| P-04 | PDF export works for a note with text and at least one image | | |
| P-05 | Service worker registers (DevTools → Application → Service Workers) | | |
| P-06 | Offline indicator appears when network is disabled in DevTools | | |
| P-07 | No JavaScript console errors on the dashboard page | | |
| P-08 | Settings page loads at `/settings` | | |
| P-09 | Change password form works correctly | | |

---

## 2. Server — Environment & Configuration

| # | Check | Status | Notes |
|---|---|---|---|
| E-01 | `SECRET_KEY` in `.env` is a cryptographically random 32+ hex character string (not the default) | | |
| E-02 | `FLASK_ENV=production` set in `.env` | | |
| E-03 | `SESSION_COOKIE_SECURE=true` set in `.env` | | |
| E-04 | `DATABASE_PATH` in `.env` points to a writable location outside the web root | | |
| E-05 | `.env` file permissions set to `640` | | |
| E-06 | `notes.db` is not accessible from the web (directory is outside web root or protected) | | |
| E-07 | `uploads/` media directory is not directly accessible via a browser URL | | |
| E-08 | `venv/` directory is not accessible via a browser URL | | |

---

## 3. HTTPS & Transport Security

| # | Check | Status | Notes |
|---|---|---|---|
| T-01 | HTTPS active; Let's Encrypt certificate valid and not expiring within 30 days | | |
| T-02 | HTTP → HTTPS redirect enabled in Plesk hosting settings | | |
| T-03 | Browser shows padlock / "Connection secure" at https://notes.defecttracker.uk | | |
| T-04 | Certificate auto-renewal confirmed (Let's Encrypt renews every 90 days) | | |
| T-05 | TLS 1.2+ enforced; TLS 1.0/1.1 disabled (Plesk SSL/TLS settings) | | |

---

## 4. HTTP Security Headers

Verify headers are present using browser DevTools → Network → select any request → Headers tab, or `curl -I https://notes.defecttracker.uk`.

| # | Header | Expected value | Status |
|---|---|---|---|
| H-01 | `X-Frame-Options` | `DENY` | |
| H-02 | `X-Content-Type-Options` | `nosniff` | |
| H-03 | `Referrer-Policy` | `strict-origin-when-cross-origin` | |
| H-04 | `Permissions-Policy` | contains `camera=()` | |
| H-05 | `Content-Security-Policy` | contains `default-src 'self'` | |
| H-06 | `Strict-Transport-Security` | Set at Apache/Plesk level (not Flask) | |

---

## 5. Authentication & Access

| # | Check | Status | Notes |
|---|---|---|---|
| A-01 | `/dashboard` redirects to `/login` when not authenticated | | |
| A-02 | Login with correct credentials redirects to `/dashboard` | | |
| A-03 | Login with incorrect password shows vague error (no hint which field is wrong) | | |
| A-04 | `/api/notes` returns `302` redirect (not `200`) when not authenticated | | |
| A-05 | Session cookie has `HttpOnly` flag set | | |
| A-06 | Session cookie has `SameSite=Lax` attribute | | |
| A-07 | Session cookie has `Secure` flag set (requires HTTPS) | | |
| A-08 | Sign out clears session and redirects to `/login` | | |

---

## 6. Functional Smoke Test

| # | Check | Status | Notes |
|---|---|---|---|
| F-01 | Create a note; reload page; note persists | | |
| F-02 | Edit note title and body; autosave fires; reload; changes persist | | |
| F-03 | Pin a note; it appears at the top of the list | | |
| F-04 | Archive a note; it moves to Archived tab | | |
| F-05 | Move note to Trash; permanently delete it | | |
| F-06 | Create a folder; move a note into it | | |
| F-07 | Add a tag to a note; filter by tag | | |
| F-08 | Search for a note by title | | |
| F-09 | Upload an image to a note; it appears inline | | |
| F-10 | Annotate an image; save; reload; annotation visible | | |
| F-11 | Export note to PDF; PDF downloads and opens correctly | | |
| F-12 | Change password via Settings page | | |

---

## 7. Backup — Pre-Go-Live

| # | Check | Status | Notes |
|---|---|---|---|
| B-01 | Manual backup of `notes.db` taken before deployment | | |
| B-02 | Backup stored in `backups/` directory outside web root | | |
| B-03 | Nightly cron job configured in Plesk Scheduled Tasks | | |
| B-04 | `uploads/` media directory included in backup (tar.gz) | | |
| B-05 | Restore procedure tested at least once from backup | | |
| B-06 | Retention policy applied (≥ 14 daily backups kept) | | |

---

## 8. Monitoring & Operations

| # | Check | Status | Notes |
|---|---|---|---|
| O-01 | Plesk error log location confirmed: `/var/www/vhosts/defecttracker.uk/logs/error_log` | | |
| O-02 | `tail -f error_log` shows no errors at idle | | |
| O-03 | Passenger process restarts correctly via `touch passenger_wsgi.py` | | |
| O-04 | App recovers correctly after a simulated restart | | |

---

## 9. Sign-Off

| Role | Name | Date | Signature |
|---|---|---|---|
| Developer | | | |
| Deployer | | | |

---

## Post-Deployment Monitoring (first 48 hours)

- Check `error_log` after 1 hour for any unexpected 500 errors.
- Verify at least one successful autosave is recorded (no errors in the log).
- Confirm the service worker is active in the browser on the production URL.
- Run the Functional Smoke Test again from a clean browser (incognito mode).
