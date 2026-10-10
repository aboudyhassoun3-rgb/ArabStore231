#!/usr/bin/env bash
# Capture desktop + mobile screenshots of the exact $CAPTURE_URL into
# $CAPTURE_DIR (outside the project source). Leaves the app running.
# Exit 75: temporary navigation/browser infrastructure failure.
# Exit 1:  script or rendering defect (e.g. screenshots missing).
set -euo pipefail

cd "$(dirname "$0")"

: "${CAPTURE_URL:?Set CAPTURE_URL to the exact preview URL.}"
: "${CAPTURE_DIR:?Set CAPTURE_DIR to the screenshot output directory.}"
: "${RUNTIME_DIR:?Set RUNTIME_DIR to the runtime scripts directory.}"

/usr/bin/time -p mkdir -p "$CAPTURE_DIR"
/usr/bin/time -p node "$RUNTIME_DIR/scripts/default-capture.mjs"
/usr/bin/time -p test -f "$CAPTURE_DIR/final-desktop.png"
/usr/bin/time -p test -f "$CAPTURE_DIR/final-mobile.png"
/usr/bin/time -p ls -la "$CAPTURE_DIR"
