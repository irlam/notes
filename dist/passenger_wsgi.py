import os, sys

APP_ROOT = os.path.dirname(__file__)
PYDEPS = os.path.join(APP_ROOT, "_pydeps")

for p in (PYDEPS, APP_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

# ---------------------------------------------------------------------------
# Ensure Pillow's compiled C extension (_imaging) is available.
#
# The repo ships the manylinux x86-64 .so files for convenience, but on
# other architectures (ARM64, etc.) or older Linux glibc versions they will
# not load.  When that happens we attempt a one-time self-heal: download the
# correct platform wheel from PyPI into _pydeps and flush PIL from the module
# cache so the new extension is picked up immediately.
# ---------------------------------------------------------------------------
def _ensure_pillow_imaging():
    try:
        from PIL import _imaging  # noqa: F401 — validates compiled extension
        return
    except ImportError:
        pass

    import subprocess
    try:
        subprocess.check_call(
            [
                sys.executable, '-m', 'pip', 'install',
                '--target', PYDEPS,
                '--upgrade', '--quiet',
                'Pillow==12.1.1',
            ],
            timeout=120,
        )
    except Exception:
        pass  # best-effort; build_pdf_bytes() will surface a clear error

    # Flush cached PIL modules so the newly installed extension is found.
    for key in list(sys.modules):
        if key.startswith('PIL'):
            del sys.modules[key]


_ensure_pillow_imaging()

from wsgi import application
