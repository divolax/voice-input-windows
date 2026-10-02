#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="${1:?Usage: build-macos.sh VERSION [arm64|x86_64]}"
ARCH="${2:-$(uname -m)}"
case "$ARCH" in
  arm64|x86_64) ;;
  *) echo "Unsupported macOS architecture: $ARCH" >&2; exit 2 ;;
esac

cd "$ROOT"
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements-build.txt
python3 -m pip install -r requirements.txt
python3 -m PyInstaller --noconfirm --clean --windowed --onedir \
  --name VoiceInput \
  --distpath "$ROOT/dist" \
  --workpath "$ROOT/build/pyinstaller-macos-$ARCH" \
  --target-arch "$ARCH" \
  --osx-bundle-identifier com.divolax.voiceinput \
  --collect-all faster_whisper \
  --collect-all ctranslate2 \
  --collect-all av \
  --collect-all sounddevice \
  --collect-all pystray \
  --collect-submodules pynput \
  --collect-all PIL \
  --collect-all huggingface_hub \
  --collect-data certifi \
  --hidden-import Quartz \
  --hidden-import ApplicationServices \
  --hidden-import CoreFoundation \
  --hidden-import Foundation \
  --hidden-import AppKit \
  --hidden-import objc \
  "$ROOT/tray_app.py"

APP="$ROOT/dist/VoiceInput.app"
if [[ ! -d "$APP" ]]; then
  echo "PyInstaller did not create $APP" >&2
  exit 1
fi

python3 - "$APP/Contents/Info.plist" "$VERSION" <<'PY'
import plistlib
import sys
from pathlib import Path

path = Path(sys.argv[1])
version = sys.argv[2]
with path.open("rb") as source:
    info = plistlib.load(source)
info.update({
    "CFBundleDisplayName": "Voice Input",
    "CFBundleName": "Voice Input",
    "CFBundleShortVersionString": version,
    "CFBundleVersion": version,
    "LSUIElement": True,
    "NSMicrophoneUsageDescription": "Voice Input uses your microphone only while you hold Control and Option to dictate.",
})
with path.open("wb") as destination:
    plistlib.dump(info, destination, sort_keys=False)
PY

# Re-sign after Info.plist is finalized; distribution remains unsigned by Apple Developer ID.
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP"
"$APP/Contents/MacOS/VoiceInput" --verify-runtime

STAGING="$ROOT/build/macos-staging-$ARCH"
mkdir -p "$ROOT/build/release-assets"
rm -rf "$STAGING"
mkdir -p "$STAGING"
ditto "$APP" "$STAGING/Voice Input.app"
ln -s /Applications "$STAGING/Applications"
DMG="$ROOT/build/release-assets/VoiceInput-${VERSION}-macos-${ARCH}.dmg"
hdiutil create -volname "Voice Input $VERSION" -srcfolder "$STAGING" -ov -format UDZO "$DMG"
shasum -a 256 "$DMG" > "${DMG}.sha256"
echo "Created $DMG"
