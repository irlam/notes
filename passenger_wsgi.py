import sys, os

sys.path.insert(0, os.path.dirname(__file__))

# Activate venv
venv_path = os.path.join(os.path.dirname(__file__), 'venv', 'lib')
if os.path.isdir(venv_path):
    for d in os.listdir(venv_path):
        site_packages = os.path.join(venv_path, d, 'site-packages')
        if os.path.isdir(site_packages):
            sys.path.insert(0, site_packages)

from wsgi import app as application
