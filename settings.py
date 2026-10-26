"""App settings, loaded via FLASK_SETTINGS_FILENAME (set in app.yaml)."""

import os

from google.cloud import secretmanager

GOOGLE_CLIENT_ID = (
    "257061274440-mmto80jtldor75l9l6kpkucdjf2fv9cn.apps.googleusercontent.com"
)


def _access_secret(secret_id):
    """Returns the latest version of a secret from Secret Manager."""
    client = secretmanager.SecretManagerServiceClient()
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    name = f"projects/{project}/secrets/{secret_id}/versions/latest"
    return client.access_secret_version(name=name).payload.data.decode()


if os.environ.get("GAE_ENV") == "standard":
    GOOGLE_CLIENT_SECRET = _access_secret("google-client-secret")
else:
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
