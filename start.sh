#!/usr/bin/env bash
# ARAB STORE — project start script (Flask backend + static ./public).
# Keeps source and built output inside PROJECT_DIR, serves in the FOREGROUND
# on $PORT (default 3000), and records deployment output for the controller.
# Worker metadata (OPENCODE_WEB_DIR) is only used for deployment-output.json.
set -euo pipefail

cd "$(dirname "$0")"
PROJECT_ROOT="$PWD"

PORT="${PORT:-3000}"
export PORT

# Built static directory inside the project (must contain index.html).
/usr/bin/time -p test -f "$PROJECT_ROOT/public/index.html"
STATIC_DIR="$PROJECT_ROOT/public"

# Install Python dependencies when needed (fast no-op when satisfied).
/usr/bin/time -p python3 -m pip install --quiet -r "$PROJECT_ROOT/requirements.txt"

/usr/bin/time -p mkdir -p "${OPENCODE_WEB_DIR:?}"

# Deployment output for the controller (absolute paths inside PROJECT_DIR).
/usr/bin/time -p python3 -c 'import json,sys; json.dump({"project": sys.argv[1], "directory": sys.argv[2]}, open(sys.argv[3], "w"))' \
  "$PROJECT_ROOT" "$STATIC_DIR" "$OPENCODE_WEB_DIR/deployment-output.json"
/usr/bin/time -p cat "$OPENCODE_WEB_DIR/deployment-output.json"
echo

# Serve in the foreground: gunicorn (single process, no reloader) preferred,
# Flask dev server as fallback when gunicorn is unavailable.
if /usr/bin/time -p python3 -c "import gunicorn" 2>/dev/null; then
  exec /usr/bin/time -p python3 -m gunicorn -b "0.0.0.0:${PORT}" --workers 1 --threads 4 --timeout 60 app:app
else
  exec /usr/bin/time -p python3 app.py
fi
