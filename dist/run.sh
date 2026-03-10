#!/bin/bash
set -e

# Create venv if needed
[ -d venv ] || python3 -m venv venv
source venv/bin/activate
pip install -q -r requirements.txt

# Copy .env.example if no .env
[ -f .env ] || cp .env.example .env

export FLASK_APP=wsgi:app
export FLASK_ENV=development
python -m flask run --host=0.0.0.0 --port=5000
