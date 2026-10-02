from __future__ import annotations

import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parent
VERSION = sys.argv[1]
OUTPUT = ROOT / "build" / "release-assets"
OUTPUT.mkdir(parents=True, exist_ok=True)

FILES = (
    "README.md",
    "SCRIPT-QUICKSTART.md",
    "dictation.py",
    "tray_app.py",
    "requirements.txt",
    "install.ps1",
    "start.ps1",
    "enable-autostart.ps1",
    "disable-autostart.ps1",
)

archive = OUTPUT / f"VoiceInput-Source-{VERSION}.zip"
with ZipFile(archive, "w", ZIP_DEFLATED, compresslevel=9) as bundle:
    for relative_path in FILES:
        bundle.write(ROOT / relative_path, relative_path)

print(archive)
