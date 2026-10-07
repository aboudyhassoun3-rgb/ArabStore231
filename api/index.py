import os
import sys

# Vercel runs this file from /api — add the project root so local
# modules (app, branding, classify) can be imported.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import app  # noqa: F401  (Vercel looks for `app` here)
