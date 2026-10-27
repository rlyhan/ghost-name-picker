"""Status code tests for the name form route."""


def assert_no_name_saved(browser):
    """Asserts the signed-in user's first and last name are still empty."""
    user = browser.user()
    assert user.first_name is None and user.last_name is None


def test_enter_name_signed_out_redirects_to_login(browser):
    assert browser.user() is None

    response = browser.get("/enter-name")

    assert response.status_code == 302
    assert response.headers["Location"] == "/login"


def test_enter_name_returns_200(ada):
    assert ada.user() is not None

    assert ada.get("/enter-name").status_code == 200


def test_enter_name_without_csrf_token_returns_403(ada):
    assert_no_name_saved(ada)

    response = ada.post(
        "/enter-name",
        {"first_name": "Ada", "last_name": "Lovelace"},
        csrf=False,
    )

    assert response.status_code == 403
    assert_no_name_saved(ada)


def test_enter_name_with_empty_name_returns_400(ada):
    assert_no_name_saved(ada)

    response = ada.post("/enter-name", {"first_name": "Ada", "last_name": ""})

    assert response.status_code == 400
    assert_no_name_saved(ada)


def test_enter_name_with_too_long_name_returns_400(ada):
    assert_no_name_saved(ada)

    response = ada.post(
        "/enter-name", {"first_name": "A" * 101, "last_name": "Lovelace"}
    )

    assert response.status_code == 400
    assert_no_name_saved(ada)


def test_enter_name_success_redirects_with_303(ada):
    assert_no_name_saved(ada)

    response = ada.post(
        "/enter-name", {"first_name": " Ada ", "last_name": "Lovelace"}
    )

    assert response.status_code == 303
    assert response.headers["Location"] == "/ghost-name-results"
    user = ada.user()
    assert (user.first_name, user.last_name) == ("Ada", "Lovelace")
