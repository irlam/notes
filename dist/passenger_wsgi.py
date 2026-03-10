import os, sys

APP_ROOT = os.path.dirname(__file__)
PYDEPS = os.path.join(APP_ROOT, "_pydeps")

for p in (PYDEPS, APP_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

# ---------------------------------------------------------------------------
# Ensure Pillow's compiled C extension (_imaging) is available.
#
# The dist/ package ships manylinux x86-64 .so files compiled for
# CPython 3.12.  They will load on any modern Linux x86-64 host running
# Python 3.12 without requiring a system-level package install.
#
# If a different Python version is in use the bundled .so files will not
# match and we attempt a one-time self-heal: download the correct platform
# wheel from PyPI into _pydeps/ and flush PIL from the module cache.
# On shared hosting without outbound pip access this fallback will fail;
# in that case the app still starts but PDF/image export will return a
# clear "Cannot import Pillow" error rather than crashing silently.
# ---------------------------------------------------------------------------
def _ensure_pillow_imaging():
    try:
        from PIL import _imaging  # noqa: F401 — validates compiled extension
        return
    except ImportError:
        pass

    import subprocess
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(
        "Pillow compiled extension not found for this Python version. "
        "The bundled _pydeps/ was built for CPython 3.12 x86-64. "
        "Attempting self-heal via pip ..."
    )
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
    except Exception as exc:
        logger.error(
            "pip install failed (%s). "
            "On shared hosting without pip access: upload a _pydeps/ folder "
            "built on a server with the same Python version using: "
            "pip install --target _pydeps -r requirements.txt",
            exc,
        )
        return  # app starts; PDF export will surface a clear error

    # Flush cached PIL modules so the newly installed extension is found.
    for key in list(sys.modules):
        if key.startswith('PIL'):
            del sys.modules[key]


_ensure_pillow_imaging()

from wsgi import application
