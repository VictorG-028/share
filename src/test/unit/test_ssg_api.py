"""
The site's service layer, read through a fake page.

The envelopes below are the real ones, captured on 2026-09-10. The three
shapes that matter are: success, an expired session, and a **successful empty
list** -- the last one because it is not a failure and treating it as one
would send the refresh down the slow path for nothing.
"""

from datetime import date

import pytest

from modules.browser import ssg_api
from modules.browser.cdp import CdpError
from modules.browser.ssg_screen import SsgLoginRequired

SESSION = "5029E521A1E1C00EF8C86497C3660EE9"
USER = "Victor Gabriel Tenorio Oliveira"

OK = {
    "IsError": False,
    "ReturnCode": "1001",
    "Message": "Operacao realizada com sucesso!",
    "ReturnObject": [
        "OSI 83385 | Faturamento Assistencial SECONCI | Homologacao End2End - Suporte - 417294",
        "coe tech - setembro - 2026 | Walber Hugo da Silva - 427465",
    ],
}
EXPIRED = {
    "IsError": True,
    "ReturnCode": "INVALID_TOKEN_3",
    "Message": "A sessao do usuario e invalida!",
    "ReturnObject": None,
}


class _FakePage:
    """Answers the two things ssg_api asks a page: cookies/fields and fetch."""

    def __init__(self, payload=None, *, cookie=SESSION, user=USER, error=None):
        self.payload = payload
        self.cookie = cookie
        self.user = user
        self.error = error
        self.calls: list[tuple] = []

    def evaluate(self, expression: str):
        if "AspSession" in expression:
            return self.cookie
        if "user-name" in expression:
            return self.user or None
        raise AssertionError(f"expressao inesperada: {expression}")

    def poll_until(self, expression, *, timeout_seconds=20, poll_seconds=0.1, on_tick=None):
        for _ in range(2):
            value = self.evaluate(expression)
            if value:
                return value
            if on_tick is not None:
                on_tick()
        return None

    def fetch_json(self, url, *, method="GET", form=None, timeout_seconds=30):
        self.calls.append((method, url, form))
        if self.error is not None:
            raise self.error
        return self.payload


def test_session_token_is_the_cookie_the_site_puts_in_its_own_routes():
    assert ssg_api.session_token(_FakePage()) == SESSION


def test_a_missing_cookie_is_not_a_crash_but_a_fallback_signal():
    with pytest.raises(ssg_api.SsgApiUnavailable):
        ssg_api.session_token(_FakePage(cookie=None))


def test_an_empty_professional_is_refused_before_it_can_lie():
    # Measured: the endpoint answers a blank userName with SUCCESS and zero
    # items, so trusting it would quietly write an empty catalog.
    with pytest.raises(ssg_api.SsgApiUnavailable):
        ssg_api.logged_user(_FakePage(user="   "))


def test_osi_labels_sends_the_day_and_returns_the_rows_verbatim():
    page = _FakePage(OK)
    labels = ssg_api.osi_labels_for(page, date(2026, 9, 10), user_name=USER)
    assert labels == OK["ReturnObject"]
    method, url, form = page.calls[0]
    assert method == "GET" and form is None
    assert SESSION in url
    assert "date=10/09/2026" in url  # the list is filtered by day on the server
    assert "term=&" in url or url.endswith("term=")


def test_an_empty_list_is_an_answer_not_a_failure():
    page = _FakePage({**OK, "ReturnObject": []})
    assert ssg_api.osi_labels_for(page, date(2026, 9, 10), user_name=USER) == []


def test_an_expired_session_asks_for_a_human_instead_of_falling_back():
    # Falling back to the DOM would only land on the login page too.
    with pytest.raises(SsgLoginRequired):
        ssg_api.osi_labels_for(_FakePage(EXPIRED), date(2026, 9, 10), user_name=USER)


def test_any_other_return_code_means_use_the_screen():
    page = _FakePage({"IsError": True, "ReturnCode": "1002", "Message": "Parameter count mismatch."})
    with pytest.raises(ssg_api.SsgApiUnavailable):
        ssg_api.osi_labels_for(page, date(2026, 9, 10), user_name=USER)


def test_a_transport_failure_also_means_use_the_screen():
    page = _FakePage(error=CdpError("conexao caiu"))
    with pytest.raises(ssg_api.SsgApiUnavailable):
        ssg_api.osi_records(page, user_name=USER)


def test_osi_records_posts_the_same_filter_the_screen_builds():
    records = [{"Id": "83385", "StatusName": "Liberado"}]
    page = _FakePage({**OK, "ReturnObject": records})
    assert ssg_api.osi_records(page, user_name=USER) == records
    method, url, form = page.calls[0]
    assert method == "POST"
    assert url.endswith("/osi/get-by-parameters")
    # OsiController.getList sends exactly UserName and nothing else.
    assert form["data"] == '{"UserName": "' + USER + '"}'


def test_records_that_are_not_objects_are_dropped():
    page = _FakePage({**OK, "ReturnObject": [{"Id": "1"}, "lixo", None]})
    assert ssg_api.osi_records(page, user_name=USER) == [{"Id": "1"}]


def test_the_professional_is_taken_from_the_first_field_that_has_a_value():
    # More than one view of the SPA carries the class, and the stale one is
    # empty right after a route change.
    assert ssg_api.logged_user(_FakePage(user=USER)) == USER
