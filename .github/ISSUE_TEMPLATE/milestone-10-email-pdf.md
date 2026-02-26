---
name: "Milestone 10 – Email PDF"
about: "Implement the Email PDF feature (send note PDF directly from the app)"
title: "[M10] Implement Email PDF — POST /api/notes/<id>/email-pdf"
labels: ["milestone-10", "enhancement", "backend", "frontend"]
assignees: []
---

## Context

Milestone 10 adds the ability to email a note's PDF export directly from the app.
The stub endpoint (`POST /api/notes/<id>/email-pdf`) is in place and returns
`403` (feature disabled) or `501` (not yet implemented).

See [`docs/milestone-10.md`](../../docs/milestone-10.md) for the full specification.

---

## Tasks

### Backend
- [ ] EP-1: Create `app/email.py` SMTP transport layer (smtplib; config from env vars)
- [ ] EP-2: Add rate limiting (max 10 emails/user/hour)
- [ ] EP-3: Note ownership check before sending
- [ ] EP-4: Generate PDF attachment using existing `app/pdf.py`
- [ ] EP-5: Compose and send email (note title as subject, PDF as attachment)
- [ ] EP-6: Migration `006_add_user_email.sql` — add `email` column to `users`
- [ ] EP-7: Update `flask create-user` CLI to accept `--email`
- [ ] EP-8: Settings page — "Email address" field for users
- [ ] EP-9: Error handling for SMTP failures → safe 500 response
- [ ] EP-10: Tests with mocked SMTP (ownership, rate-limit, success, failure)

### Frontend
- [ ] EP-F1: Enable `btn-email-pdf` button when feature is active
- [ ] EP-F2: Show "Sending…" state on click
- [ ] EP-F3: Show success toast on 200
- [ ] EP-F4: Show error toast on failure

---

## Acceptance Criteria

- [ ] Authenticated user can email a PDF of any of their own notes
- [ ] Email sent to address stored in user profile
- [ ] Rate limit enforced; excess returns 429
- [ ] Other user's notes return 404
- [ ] SMTP errors return safe 500; credentials never leaked
- [ ] All tests pass with mocked SMTP

---

## Security Notes

- SMTP credentials from `.env` only; never log or return them
- Recipient restricted to authenticated user's stored address (no open relay)
- Subject line is server-generated from note title (HTML-stripped)

---

## Related

- [`docs/milestone-10.md`](../../docs/milestone-10.md)
- Stub: `app/email_export.py`
- Issue template: `.github/ISSUE_TEMPLATE/milestone-10-batch-export.md`
