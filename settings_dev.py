"""Local development settings, loaded via FLASK_SETTINGS_FILENAME.

Setting SECRET_KEY stops securescaffold from fetching one from Datastore.
"""

from settings import *  # pylint: disable=wildcard-import,unused-wildcard-import
SECRET_KEY = "dev-only-not-secret"

CSRF_COOKIE_SECURE = False
