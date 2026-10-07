#!/usr/bin/env bash
# ARAB STORE — project start script (Flask + static dist).
# - Builds a static snapshot into $PROJECT_DIR/dist (index.html guaranteed).
# - Writes $OPENCODE_WEB_DIR/deployment-output.json {project, directory}.
# - Installs Python deps, then serves the Flask app in the FOREGROUND on $PORT (default 3000).
set -euo pipefail
cd "$(dirname "$0")"
/usr/bin/time -p pwd
PROJECT_ROOT="$(pwd)"
PORT="${PORT:-3000}"
export PORT
DIST_DIR="$PROJECT_ROOT/dist"
/usr/bin/time -p mkdir -p "$DIST_DIR"
/usr/bin/time -p rm -rf "$DIST_DIR"
/usr/bin/time -p mkdir -p "$DIST_DIR"
/usr/bin/time -p cp -r "$PROJECT_ROOT/public/." "$DIST_DIR/"
/usr/bin/time -p test -f "$DIST_DIR/index.html"
/usr/bin/time -p python3 -m pip install --quiet -r "$PROJECT_ROOT/requirements.txt"
/usr/bin/time -p python3 -c "import flask, flask_limiter; print('deps ok')"
OPENCODE_WEB_DIR="${OPENCODE_WEB_DIR:?OPENCODE_WEB_DIR must be set}"
/usr/bin/time -p python3 - "$PROJECT_ROOT" "$DIST_DIR" "$OPENCODE_WEB_DIR/deployment-output.json" <<'PY'
import json, sys
project, directory, out = sys.argv[1], sys.argv[2], sys.argv[3]
with open(out, "w") as fh:
    json.dump({"project": project, "directory": directory}, fh)
print("wrote", out)
PY
/usr/bin/time -p cat "$OPENCODE_WEB_DIR/deployment-output.json"
/usr/bin/time -p python3 "$PROJECT_ROOT/app.py"
