"""App settings, loaded via FLASK_SETTINGS_FILENAME (set in app.yaml)."""

import os

GOOGLE_CLIENT_ID = (
    "257061274440-mmto80jtldor75l9l6kpkucdjf2fv9cn.apps.googleusercontent.com"
)
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
