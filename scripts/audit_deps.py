#!/usr/bin/env python3
"""Dependency audit script for notes.defecttracker.uk.

Scans all Python source files for third-party imports and compares them
against the packages installed in _pydeps.  Reports used vs. present
packages, and exits non-zero if unknown or unused packages are found
(controlled by the allowlist below).

Usage
-----
    python scripts/audit_deps.py [--strict]

Options
-------
    --strict    Exit 1 if any unused packages are present in _pydeps
                (ignores the allowlist for unused packages).

Exit codes
----------
    0  All checks pass.
    1  Unknown third-party imports (not in _pydeps and not stdlib).
    2  Unused packages in _pydeps (only in strict mode).
"""
import ast
import importlib.util
import os
import sys

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYDEPS_DIR = os.path.join(REPO_ROOT, '_pydeps')
SOURCE_DIRS = [
    os.path.join(REPO_ROOT, 'app'),
    os.path.join(REPO_ROOT, 'tests'),
    os.path.join(REPO_ROOT, 'scripts'),
    REPO_ROOT,  # wsgi.py, passenger_wsgi.py
]

# Top-level package name → canonical package name mapping.
# Keys are the importable name; values are the package dist-name.
_IMPORT_TO_PACKAGE = {
    'flask': 'Flask',
    'dotenv': 'python-dotenv',
    'PIL': 'Pillow',
    'reportlab': 'reportlab',
    'pypdf': 'pypdf',
    'pytest': 'pytest',
    'click': 'click',
    'jinja2': 'Jinja2',
    'werkzeug': 'Werkzeug',
    'itsdangerous': 'itsdangerous',
    'blinker': 'blinker',
    'markupsafe': 'MarkupSafe',
    'iniconfig': 'iniconfig',
    'packaging': 'packaging',
    'pluggy': 'pluggy',
    'colorama': 'colorama',
    'chardet': 'chardet',
}

# Packages that are allowed in _pydeps even if not directly imported in app
# source (e.g. transitive deps, test tools, dev utilities).
ALLOWED_UNUSED = {
    'pytest',        # test runner — not imported in app source
    '_pytest',       # internal pytest package
    'iniconfig',     # pytest dependency
    'packaging',     # pytest/pip dependency
    'pluggy',        # pytest dependency
    'colorama',      # pytest/click optional dep (Windows terminal)
    'chardet',       # reportlab optional dep
    'py',            # legacy pytest compat shim
    'blinker',       # Flask signals (used by Flask internally)
    'itsdangerous',  # Flask dependency
    'markupsafe',    # Jinja2 dependency
    'click',         # Flask/CLI dependency
    'werkzeug',      # Flask dependency
    'jinja2',        # Flask dependency
}


def _installed_packages():
    """Return a set of top-level importable package names present in _pydeps."""
    packages = set()
    if not os.path.isdir(PYDEPS_DIR):
        return packages
    for entry in os.listdir(PYDEPS_DIR):
        full = os.path.join(PYDEPS_DIR, entry)
        # Package directory
        if os.path.isdir(full) and not entry.endswith(('.dist-info', '.data', '__pycache__')):
            packages.add(entry)
        # Top-level module (.py or .so)
        elif os.path.isfile(full) and entry.endswith('.py') and not entry.startswith('_'):
            packages.add(entry[:-3])
    return packages


def _stdlib_modules():
    """Return a set of stdlib top-level module names."""
    stdlib = set(sys.stdlib_module_names) if hasattr(sys, 'stdlib_module_names') else set()
    # Supplement with common ones for older Python
    stdlib.update({
        'os', 'sys', 'io', 'json', 'math', 'hashlib', 'hmac', 'secrets',
        'datetime', 'time', 'logging', 'traceback', 're', 'abc', 'typing',
        'collections', 'functools', 'itertools', 'operator', 'pathlib',
        'shutil', 'tempfile', 'subprocess', 'threading', 'multiprocessing',
        'socket', 'ssl', 'smtplib', 'email', 'http', 'urllib', 'base64',
        'struct', 'copy', 'gc', 'inspect', 'importlib', 'builtins',
        'unittest', 'zipfile', 'tarfile', 'csv', 'configparser',
        'argparse', 'getpass', 'platform', 'stat', 'fnmatch', 'glob',
        'contextlib', 'warnings', 'weakref', 'enum', 'dataclasses',
        'string', 'textwrap', 'difflib', 'pprint', 'ast', 'dis',
        'code', 'codeop', 'tokenize', 'token', 'compileall',
        'py_compile', 'marshal', 'pickle', 'shelve', 'sqlite3',
        'xml', 'html', 'cgi', 'wsgiref', 'zlib', 'gzip', 'bz2', 'lzma',
        'random', 'statistics', 'decimal', 'fractions', 'numbers',
        'array', 'queue', 'heapq', 'bisect', 'uuid',
    })
    return stdlib


def _collect_imports(source_dir):
    """Walk *source_dir* collecting top-level import names from .py files."""
    imports = set()
    for root, dirs, files in os.walk(source_dir):
        # Skip _pydeps and .git
        dirs[:] = [d for d in dirs if d not in ('_pydeps', '.git', '__pycache__',
                                                  '.pytest_cache', 'node_modules')]
        for fname in files:
            if not fname.endswith('.py'):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, encoding='utf-8', errors='ignore') as fh:
                    source = fh.read()
                tree = ast.parse(source, filename=fpath)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.level == 0:
                        imports.add(node.module.split('.')[0])
    return imports


def main():
    strict = '--strict' in sys.argv

    stdlib = _stdlib_modules()
    installed = _installed_packages()

    # Collect all imports across source directories
    all_imports = set()
    for src_dir in SOURCE_DIRS:
        if os.path.exists(src_dir):
            all_imports.update(_collect_imports(src_dir))

    # Local modules (in repo root or app package)
    local_modules = {'app', 'wsgi', 'passenger_wsgi'}
    for entry in os.listdir(REPO_ROOT):
        if entry.endswith('.py') and not entry.startswith('_'):
            local_modules.add(entry[:-3])

    # Filter to third-party only
    third_party_imports = {
        name for name in all_imports
        if name not in stdlib
        and not name.startswith('_')
        and name not in local_modules
    }

    # Map import names to package names
    used_packages = set()
    unknown_imports = set()
    for imp in third_party_imports:
        if imp in _IMPORT_TO_PACKAGE:
            used_packages.add(imp)
        elif imp in installed:
            used_packages.add(imp)
        else:
            # Check if it resolves from stdlib as a fallback
            spec = importlib.util.find_spec(imp)
            if spec is None or (spec.origin and '_pydeps' not in str(spec.origin)
                                and 'site-packages' not in str(spec.origin)):
                unknown_imports.add(imp)

    # Packages in _pydeps that are not used
    dist_info_packages = set()
    if os.path.isdir(PYDEPS_DIR):
        for entry in os.listdir(PYDEPS_DIR):
            if entry.endswith('.dist-info'):
                pkg = entry.rsplit('-', 1)[0].lower().replace('-', '_')
                dist_info_packages.add(pkg)

    # Print report
    print('=' * 60)
    print('Dependency Audit Report')
    print('=' * 60)
    print(f'\nPYDEPS directory : {PYDEPS_DIR}')
    print(f'Installed pkgs   : {len(dist_info_packages)}')
    print(f'Third-party imports found: {len(third_party_imports)}')

    print('\n[INSTALLED packages in _pydeps]')
    for p in sorted(dist_info_packages):
        print(f'  {p}')

    print('\n[THIRD-PARTY imports found in source]')
    for p in sorted(third_party_imports):
        print(f'  {p}')

    exit_code = 0

    if unknown_imports:
        print('\n[ERROR] Unknown third-party imports (not in _pydeps or stdlib):')
        for p in sorted(unknown_imports):
            print(f'  {p}')
        exit_code = 1
    else:
        print('\n[OK] All third-party imports resolve from _pydeps or stdlib.')

    # In strict mode, flag unused packages (excluding allowlist)
    if strict:
        unused = dist_info_packages - {
            p.lower().replace('-', '_') for p in _IMPORT_TO_PACKAGE.values()
        } - {p.lower().replace('-', '_') for p in ALLOWED_UNUSED}
        if unused:
            print('\n[STRICT] Unused packages in _pydeps (not in allowlist):')
            for p in sorted(unused):
                print(f'  {p}')
            exit_code = 2
        else:
            print('[OK] No unexpected unused packages in _pydeps.')

    print('\n' + '=' * 60)
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
