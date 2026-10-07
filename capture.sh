#!/usr/bin/env bash
# ARAB STORE — capture script.
# Captures desktop + mobile screenshots of $CAPTURE_URL into $CAPTURE_DIR
# as final-desktop.png / final-mobile.png. Leaves the app running.
# Exit 75 = temporary navigation/browser infra failure; exit 1 = script/rendering defect.
set -euo pipefail
cd "$(dirname "$0")"
if [[ -z "${CAPTURE_URL:-}" ]]; then echo "CAPTURE_URL must be set" >&2; exit 1; fi
if [[ -z "${CAPTURE_DIR:-}" ]]; then echo "CAPTURE_DIR must be set" >&2; exit 1; fi
if [[ "$CAPTURE_DIR" == "$(pwd)"* ]]; then echo "CAPTURE_DIR must be outside the project source" >&2; exit 1; fi
/usr/bin/time -p mkdir -p "$CAPTURE_DIR"
/usr/bin/time -p node "${RUNTIME_DIR:?RUNTIME_DIR must be set}/scripts/default-capture.mjs"
/usr/bin/time -p test -f "$CAPTURE_DIR/final-desktop.png"
/usr/bin/time -p test -f "$CAPTURE_DIR/final-mobile.png"
/usr/bin/time -p ls -la "$CAPTURE_DIR"
