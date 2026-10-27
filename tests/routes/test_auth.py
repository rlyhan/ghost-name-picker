"""Status code tests for the sign-in and sign-out routes."""

import urllib.parse

import models


def test_login_redirects_to_google(browser):
    assert browser.user() is None

    response = browser.get("/login")

    assert response.status_code == 302
    location = urllib.parse.urlparse(response.headers["Location"])
    assert location.netloc == "accounts.google.com"


def test_login_when_signed_in_redirects_to_overview(ada):
    assert ada.user() is not None

    response = ada.get("/login")

    assert response.status_code == 302
    assert response.headers["Location"] == "/"


def test_auth_callback_with_forged_state_returns_401(browser):
    assert browser.user() is None

    response = browser.get("/auth/callback?state=forged&code=fake")

    assert response.status_code == 401
    assert browser.user() is None


def test_auth_callback_with_unverified_email_returns_401(browser, datastore):
    assert browser.user() is None

    response = browser.sign_in("sub", "a@example.com", email_verified=False)

    assert response.status_code == 401
    assert browser.user() is None
    with datastore.context():
        assert models.User.get_by_id("sub") is None


def test_auth_callback_success_redirects_to_overview(browser):
    assert browser.user() is None

    response = browser.sign_in("sub", "a@example.com")

    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    user = browser.user()
    assert user.google_auth_id == "sub"
    assert user.email_address == "a@example.com"


def test_logout_without_csrf_token_returns_403(ada):
    assert ada.user() is not None

    response = ada.post("/logout", csrf=False)

    assert response.status_code == 403
    assert ada.user() is not None


def test_logout_redirects_with_303(ada):
    assert ada.user() is not None

    response = ada.post("/logout")

    assert response.status_code == 303
    assert response.headers["Location"] == "/"
    assert ada.user() is None
