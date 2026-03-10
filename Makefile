.PHONY: dist clean test run lint help

# Default target
.DEFAULT_GOAL := help

# ─────────────────────────────────────────────
#  Help
# ─────────────────────────────────────────────
help:
	@echo ""
	@echo "Notes App — Makefile targets"
	@echo ""
	@echo "  make dist        Build a deployment-ready dist/ folder"
	@echo "  make dist-zip    Build dist/ and create notes-app.zip"
	@echo "  make clean       Remove the dist/ folder and zip archive"
	@echo "  make run         Start the development server (bash run.sh)"
	@echo "  make test        Run the full test suite (pytest)"
	@echo "  make lint        Run the Python linter (flake8, if installed)"
	@echo "  make install     Run install.sh in development mode"
	@echo ""

# ─────────────────────────────────────────────
#  Build distribution package
# ─────────────────────────────────────────────
dist:
	@echo "Building distribution package in dist/ ..."
	@rm -rf dist/
	@mkdir -p dist/

	@# Application source
	@cp -r app dist/app

	@# Database files
	@cp schema.sql dist/schema.sql
	@cp -r db dist/db
	@cp -r migrations dist/migrations

	@# Helper scripts
	@cp -r scripts dist/scripts

	@# Web server and WSGI entry points
	@cp passenger_wsgi.py dist/passenger_wsgi.py
	@cp wsgi.py dist/wsgi.py
	@cp .htaccess dist/.htaccess

	@# Python dependencies list and bundled packages
	@cp requirements.txt dist/requirements.txt
	@# Note: _pydeps/ is intentionally excluded from dist.
	@#       Run 'pip install --target _pydeps -r requirements.txt' on the
	@#       target server (or use 'bash install.sh --plesk') to build it
	@#       for the correct platform architecture.

	@# Environment template
	@cp .env.example dist/.env.example

	@# Installation and startup scripts
	@cp install.sh dist/install.sh
	@cp run.sh dist/run.sh

	@# Documentation
	@cp README.md dist/README.md
	@cp DEPLOYMENT.md dist/DEPLOYMENT.md
	@cp CHANGELOG.md dist/CHANGELOG.md

	@# Dist-specific .gitignore (prevents accidental commits of runtime files)
	@printf 'venv/\n__pycache__/\n*.pyc\n.env\n*.db\nuploads/\n*.log\n.DS_Store\nnotes-app.zip\n' > dist/.gitignore

	@# Ensure scripts are executable
	@chmod +x dist/install.sh dist/run.sh dist/scripts/db_init.sh dist/scripts/db_reset_dev.sh

	@# Remove any Python cache files that snuck in
	@find dist/ -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find dist/ -name '*.pyc' -delete 2>/dev/null || true

	@echo ""
	@echo "  dist/ is ready for deployment."
	@echo "  To create a ZIP archive run:  make dist-zip"
	@echo ""

# ─────────────────────────────────────────────
#  Build dist and create a zip archive
# ─────────────────────────────────────────────
dist-zip: dist
	@echo "Creating notes-app.zip ..."
	@zip -qr notes-app.zip dist/
	@echo "  notes-app.zip created ($(du -sh notes-app.zip | cut -f1))"

# ─────────────────────────────────────────────
#  Clean build artefacts
# ─────────────────────────────────────────────
clean:
	rm -rf dist/
	rm -f notes-app.zip
	@echo "Cleaned."

# ─────────────────────────────────────────────
#  Development helpers
# ─────────────────────────────────────────────
run:
	bash run.sh

test:
	python -m pytest tests/ -v

lint:
	@command -v flake8 >/dev/null 2>&1 \
		&& flake8 app/ --max-line-length=120 \
		|| echo "flake8 not installed — skipping lint"

install:
	bash install.sh --dev
