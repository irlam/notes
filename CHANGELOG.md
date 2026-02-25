# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned
- Sync status indicator (saved / saving / error states)
- Image annotation (inline drawing on attached images)
- PDF export of individual notes
- Rich-text / Markdown editing
- Search / filter notes by keyword
- Note tagging / colour coding
- Multi-user authentication (future milestone)

---

## [0.1.0] — 2024-Q4

### Added
- Two-pane layout: note list (left) + editor (right)
- Autosave with 1.5 s debounce
- PWA manifest and service worker (offline app-shell caching)
- Offline indicator banner
- Touch-friendly UI (minimum 44 px tap targets)
- Delete confirmation dialog
- REST API: list, create, get, update, delete notes
- SQLite backend with `user_id` column (single-user default, multi-user ready)
- Plesk / Passenger WSGI deployment support (`passenger_wsgi.py`)
- Environment variable configuration via `.env`

### Deployment target
- notes.defecttracker.uk (Plesk, Passenger WSGI, no Docker)
