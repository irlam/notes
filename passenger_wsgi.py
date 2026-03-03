import os, sys

APP_ROOT = os.path.dirname(__file__)
PYDEPS = os.path.join(APP_ROOT, "_pydeps")

for p in (PYDEPS, APP_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from wsgi import application
