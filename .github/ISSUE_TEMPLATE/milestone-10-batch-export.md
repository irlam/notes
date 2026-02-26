---
name: "Milestone 10 – Batch Export"
about: "Implement the Batch Export feature (ZIP of PDFs or combined PDF for multiple notes)"
title: "[M10] Implement Batch Export — POST /api/batch-export"
labels: ["milestone-10", "enhancement", "backend", "frontend"]
assignees: []
---

## Context

Milestone 10 adds the ability to batch-export multiple notes as either a ZIP
archive (one PDF per note) or a single combined PDF.
The stub endpoint (`POST /api/batch-export`) is in place and returns
`403` (feature disabled) or `501` (not yet implemented).

See [`docs/milestone-10.md`](../../docs/milestone-10.md) for the full specification.

---

## Tasks

### Backend
- [ ] BE-1: Implement `POST /api/batch-export` — accept `{"note_ids": [...], "format": "zip|pdf"}`
- [ ] BE-2: Input validation — max 50 note IDs; all must belong to the current user
- [ ] BE-3: Generate per-note PDFs using existing `app/pdf.py`
- [ ] BE-4: ZIP format — in-memory `zipfile.ZipFile`; one `<title>.pdf` per note
- [ ] BE-5: Combined PDF format — merged pages via ReportLab
- [ ] BE-6: Stream response with `Content-Disposition: attachment`
- [ ] BE-7: Tests — ownership, size cap, ZIP content, combined PDF content

### Frontend
- [ ] BE-F1: "Select notes" mode in sidebar (checkboxes)
- [ ] BE-F2: "📦 Batch Export" button visible when ≥1 note is selected
- [ ] BE-F3: Format picker dialog (ZIP vs combined PDF)
- [ ] BE-F4: POST to API; trigger download via blob URL
- [ ] BE-F5: Clear selection after download

---

## Acceptance Criteria

- [ ] User can export 1–50 notes in one request
- [ ] ZIP contains one correctly named PDF per note
- [ ] Combined PDF contains all notes separated by page breaks
- [ ] Other user's notes return 404
- [ ] > 50 notes returns 400
- [ ] Empty `note_ids` returns 400
- [ ] Download has correct `Content-Disposition: attachment` header

---

## Security Notes

- All note IDs verified for ownership before processing
- Filenames in ZIP sanitised (no path traversal)
- Batch size cap (50) to prevent DoS / memory exhaustion

---

## Related

- [`docs/milestone-10.md`](../../docs/milestone-10.md)
- Stub: `app/email_export.py`
- Issue template: `.github/ISSUE_TEMPLATE/milestone-10-email-pdf.md`
