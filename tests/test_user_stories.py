"""User story tests for the name form, results page and overview."""

import re
from concurrent import futures

from google.cloud import ndb

import main
import models


def submit_name(browser):
    """Fills in the name form and follows the redirect to the results."""
    response = browser.post(
        "/enter-name", {"first_name": "Ada", "last_name": "Lovelace"}
    )
    assert response.status_code == 303
    assert browser.user().first_name == "Ada"
    return browser.get(response.headers["Location"])


def options(response):
    """Returns (ghost name ID, label) pairs offered on the results page."""
    return re.findall(
        r'value="([^"]+)"\s*/>\s*<label[^>]*>([^<]+)</label>', response.text
    )


def links(response):
    """Returns the text of every link on a page."""
    return re.findall(r"<a [^>]*>([^<]+)</a>", response.text)


def test_signed_out_visitor_must_sign_in_to_get_a_phantom_name(browser):
    assert browser.user() is None
    assert "Get a Phantom Name" in links(browser.get("/"))

    response = browser.get("/enter-name")

    assert response.headers["Location"] == "/login"


def test_user_sees_a_form_for_first_and_last_name(ada):
    response = ada.get("/enter-name")

    assert 'name="first_name"' in response.text
    assert 'name="last_name"' in response.text


def test_user_sees_an_error_if_first_or_last_name_is_empty(ada):
    for first_name, last_name in [("", "Lovelace"), ("Ada", ""), (" ", " ")]:
        response = ada.post(
            "/enter-name", {"first_name": first_name, "last_name": last_name}
        )

        assert "Please enter both your first name and last name." in (
            response.text
        )


def test_user_sees_up_to_3_ghost_names_formatted_with_their_name(ada):
    offered = options(submit_name(ada))

    assert len(offered) == 3
    assert len({ghost_id for ghost_id, _ in offered}) == 3
    for _, label in offered:
        assert re.fullmatch(r"Ada \S+ Lovelace", label)


def test_user_sees_fewer_options_when_fewer_ghost_names_are_left(
    ada, datastore, ghost_names
):
    with datastore.context():
        ndb.delete_multi(ghost_names[2:])

    assert len(options(submit_name(ada))) == 2


def test_user_picks_a_ghost_name_and_sees_it_on_the_overview(ada):
    assert "Get a Phantom Name" in links(ada.get("/"))
    ghost_id, label = options(submit_name(ada))[0]

    response = ada.post("/ghost-name-results", {"ghost_name": ghost_id})
    overview = ada.get(response.headers["Location"])

    assert f"Your ghost name: {label}" in " ".join(overview.text.split())
    assert "Change your current Phantom name" in links(overview)
    assert "Get a Phantom Name" not in links(overview)


def test_overview_shows_name_and_email_of_user_who_took_a_ghost_name(ada):
    ghost_id, _ = options(submit_name(ada))[0]
    ada.post("/ghost-name-results", {"ghost_name": ghost_id})

    overview = ada.get("/")

    assert "Ada Lovelace (ada@example.com)" in overview.text


def test_changing_ghost_name_releases_the_previous_one(ada, datastore):
    first_id, _ = options(submit_name(ada))[0]
    ada.post("/ghost-name-results", {"ghost_name": first_id})
    with datastore.context():
        assert models.GhostName.get_by_id(first_id).user_id.id() == "ada-sub"
    new_options = options(ada.get("/ghost-name-results"))
    assert first_id not in [ghost_id for ghost_id, _ in new_options]
    second_id, _ = new_options[0]

    ada.post("/ghost-name-results", {"ghost_name": second_id})

    with datastore.context():
        user = models.User.get_by_id("ada-sub")
        assert user.ghost_name.id() == second_id
        assert models.GhostName.get_by_id(second_id).user_id == user.key
        assert models.GhostName.get_by_id(first_id).user_id is None


def test_user_cannot_select_a_ghost_name_when_all_are_taken(
    ada, browser, datastore, ghost_names
):
    grace = browser
    grace.sign_in("grace-sub", "grace@example.com")
    grace_key = grace.user().key
    with datastore.context():
        ghosts = ndb.get_multi(ghost_names)
        for ghost in ghosts:
            ghost.user_id = grace_key
        ndb.put_multi(ghosts)

    response = submit_name(ada)

    assert "Sorry, all ghost names have been taken." in response.text
    assert 'type="radio"' not in response.text


def test_two_users_cannot_take_the_same_ghost_name(ada, browser, datastore):
    grace = browser
    grace.sign_in("grace-sub", "grace@example.com")
    with datastore.context():
        casper = ndb.Key(models.GhostName, "casper")

    def claim(user):
        with datastore.context():
            return main.choose_ghost_name(user.key, casper)

    with futures.ThreadPoolExecutor() as pool:
        ada_won, grace_won = pool.map(claim, [ada.user(), grace.user()])

    assert [ada_won, grace_won].count(True) == 1
    owners = [ada.user().ghost_name, grace.user().ghost_name]
    assert owners.count(casper) == 1
