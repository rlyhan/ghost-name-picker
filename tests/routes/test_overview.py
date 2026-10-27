"""Status code tests for the overview route."""


def test_overview_returns_200(browser):
    assert browser.get("/").status_code == 200
