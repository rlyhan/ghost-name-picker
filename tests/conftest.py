"""Pytest fixtures: an in-memory Datastore emulator and signed-in clients.

The emulator starts once per test session on a free port with its own data
directory, so tests never touch the development emulator or its data, and is
reset before each test.
"""

import os
import re
import socket
import tempfile
import urllib.request
from unittest import mock

import pytest
from securescaffold import emulator

BASE_URL = "https://localhost"


def _free_port():
    """Returns a TCP port that is currently free on localhost."""
    with socket.socket() as sock:
        sock.bind(("localhost", 0))
        return sock.getsockname()[1]


_emulator = emulator.DatastoreEmulatorForTests(
    host_port=f"localhost:{_free_port()}",
    data_dir=tempfile.mkdtemp(prefix="ghost-name-picker-tests-"),
)
_emulator.start()
os.environ["FLASK_SETTINGS_FILENAME"] = "settings_dev.py"
os.environ["GOOGLE_CLIENT_SECRET"] = "test-secret"

# pylint: disable=wrong-import-position
from google.cloud import ndb  # noqa: E402

import main  # noqa: E402
import models  # noqa: E402


def pytest_sessionfinish():
    """Stops the emulator once all tests have run."""
    _emulator.stop()


@pytest.fixture(autouse=True)
def reset_datastore():
    """Empties the emulator before each test."""
    request = urllib.request.Request(
        os.environ["DATASTORE_HOST"] + "/reset", method="POST"
    )
    with urllib.request.urlopen(request):
        pass


@pytest.fixture(name="datastore")
def fixture_datastore():
    """An NDB client; use `with datastore.context():` outside of requests."""
    return ndb.Client()


@pytest.fixture(name="ghost_names")
def fixture_ghost_names(datastore):
    """Seeds five ghost names and returns their keys."""
    names = ["Betelgeuse", "Casper", "Draugr", "Slimer", "Zuul"]
    with datastore.context():
        return ndb.put_multi(
            [
                models.GhostName(
                    id=name.lower(), name=name, description=f"{name}."
                )
                for name in names
            ]
        )


class Browser:
    """A test client that remembers its CSRF token, like a real browser."""

    def __init__(self):
        self.client = main.app.test_client()

    def get(self, path):
        """Sends a GET request."""
        return self.client.get(path, base_url=BASE_URL)

    def post(self, path, data=None, csrf=True):
        """Sends a POST, with the CSRF token from the page unless csrf=False."""
        data = dict(data or {})
        if csrf:
            data["_csrf_token"] = self.csrf_token()
        return self.client.post(
            path,
            base_url=BASE_URL,
            data=data,
            headers={"Referer": BASE_URL + "/"},
        )

    def session(self):
        """Returns a copy of the browser's current Flask session."""
        with self.client.session_transaction() as session:
            return dict(session)

    def user(self):
        """Returns the signed-in User from Datastore, or None if signed out."""
        google_auth_id = self.session().get("google_auth_id")
        if not google_auth_id:
            return None
        with ndb.Client().context():
            return models.User.get_by_id(google_auth_id)

    def csrf_token(self):
        """Reads the CSRF token from the name form (requires sign-in)."""
        html = self.get("/enter-name").get_data(as_text=True)
        match = re.search(r'name="_csrf_token" value="([^"]+)"', html)
        return match.group(1)

    def sign_in(self, sub, email, email_verified=True):
        """Completes Google sign-in with a stubbed token exchange."""
        userinfo = {
            "sub": sub,
            "email": email,
            "email_verified": email_verified,
        }
        with mock.patch.object(
            main.google,
            "authorize_access_token",
            return_value={"userinfo": userinfo},
        ):
            return self.get("/auth/callback")


@pytest.fixture(name="browser")
def fixture_browser():
    """A signed-out browser."""
    return Browser()


@pytest.fixture(name="ada")
def fixture_ada(ghost_names):  # pylint: disable=unused-argument
    """A browser signed in as Ada, with ghost names seeded."""
    browser = Browser()
    browser.sign_in("ada-sub", "ada@example.com")
    return browser
