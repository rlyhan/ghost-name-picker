"""Status code tests for the ghost name results route."""

import re

from google.cloud import ndb

import main
import models


def offered_ids(response):
    """Returns the ghost name IDs offered as radio buttons on a page."""
    return re.findall(r'name="ghost_name"\s+value="([^"]+)"', response.text)


def enter_name(browser):
    """Submits a valid name so the results page is reachable."""
    assert browser.user() is not None
    response = browser.post(
        "/enter-name", {"first_name": "Ada", "last_name": "Lovelace"}
    )
    assert response.status_code == 303
    assert browser.user().first_name == "Ada"


def owner_of(datastore, ghost_id):
    """Returns the ID of the user a ghost name is assigned to, or None."""
    with datastore.context():
        user_key = models.GhostName.get_by_id(ghost_id).user_id
        return user_key and user_key.id()


def test_results_signed_out_redirects_to_login(browser):
    assert browser.user() is None

    response = browser.get("/ghost-name-results")

    assert response.status_code == 302
    assert response.headers["Location"] == "/login"


def test_results_without_name_redirects_to_enter_name(ada):
    user = ada.user()
    assert user.first_name is None and user.last_name is None

    response = ada.get("/ghost-name-results")

    assert response.status_code == 302
    assert response.headers["Location"] == "/enter-name"


def test_results_returns_200(ada):
    enter_name(ada)

    assert ada.get("/ghost-name-results").status_code == 200


def test_choose_without_selection_returns_400(ada):
    enter_name(ada)
    ada.get("/ghost-name-results")

    response = ada.post("/ghost-name-results")

    assert response.status_code == 400
    assert ada.user().ghost_name is None


def test_choose_ghost_name_not_shown_to_user_returns_400(
    ada, ghost_names, datastore
):
    enter_name(ada)
    seeded = [key.id() for key in ghost_names]
    shown = offered_ids(ada.get("/ghost-name-results"))
    not_shown = [name for name in seeded if name not in shown]
    assert len(shown) == 3 and len(not_shown) == 2
    choice = not_shown[0]
    assert owner_of(datastore, choice) is None

    response = ada.post("/ghost-name-results", {"ghost_name": choice})

    assert response.status_code == 400
    assert ada.user().ghost_name is None
    assert owner_of(datastore, choice) is None


def test_choose_ghost_name_already_taken_by_another_user_returns_409(
    ada, datastore
):
    enter_name(ada)
    choice = offered_ids(ada.get("/ghost-name-results"))[0]
    with datastore.context():
        grace = models.User(
            id="grace-sub",
            google_auth_id="grace-sub",
            email_address="grace@example.com",
        )
        grace.put()
        main.choose_ghost_name(grace.key, ndb.Key(models.GhostName, choice))
    assert owner_of(datastore, choice) == "grace-sub"

    response = ada.post("/ghost-name-results", {"ghost_name": choice})

    assert response.status_code == 409
    assert owner_of(datastore, choice) == "grace-sub"
    assert ada.user().ghost_name is None


def test_choose_ghost_name_success_redirects_with_303(ada, datastore):
    enter_name(ada)
    choice = offered_ids(ada.get("/ghost-name-results"))[0]
    assert owner_of(datastore, choice) is None

    response = ada.post("/ghost-name-results", {"ghost_name": choice})

    assert response.status_code == 303
    assert response.headers["Location"] == "/"
    assert ada.user().ghost_name.id() == choice
    assert owner_of(datastore, choice) == ada.user().google_auth_id
