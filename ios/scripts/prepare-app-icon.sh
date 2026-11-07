#!/bin/sh
# Create Xcode-compatible 1024px PNG only if the full-resolution icon is missing.
set -eu
APPICON_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/../ViePNMobile/Assets.xcassets/AppIcon.appiconset" && pwd)"
PNG="$APPICON_DIR/AppIcon-1024.png"
JPEG="$APPICON_DIR/Source-Icon.jpg"
if [ -s "$PNG" ]; then
  echo "Using existing full-quality AppIcon-1024.png"
  exit 0
fi
if [ ! -s "$JPEG" ]; then
  echo "ERROR: Icon source is missing: $JPEG" >&2
  exit 2
fi
if ! command -v sips >/dev/null 2>&1; then
  echo "ERROR: macOS sips utility is required to prepare the icon" >&2
  exit 2
fi
sips -s format png -z 1024 1024 "$JPEG" --out "$PNG" >/dev/null
test -s "$PNG"
echo "AppIcon-1024.png generated from compact logo preview"
