"""
Decoding an HTTP answer by the charset it declares.

The bytes are the real ones: the SSG answers ``charset=Windows-1252``
(measured 2026-10-02), where ``ç`` is ``E7`` and ``ã`` is ``E3``.
"""

import base64
import json

from modules.browser.body_text import declared_charset, decode_body
from modules.browser.cdp import CdpPage

CP1252 = "text/json; charset=Windows-1252"
LABEL = "OSI 83685 | Faturamento Assistencial SECONCI | Preparação Operação Assistida - 417487"


def test_windows_1252_bytes_decode_to_the_accented_letters():
    assert decode_body(b"Prepara\xe7\xe3o", CP1252) == "Preparação"


def test_the_same_bytes_read_as_utf8_are_the_bug_this_fixes():
    # What ``Response.text()`` did: one U+FFFD per accented letter.
    assert b"Prepara\xe7\xe3o".decode("utf-8", errors="replace") == "Prepara��o"


def test_no_declared_charset_means_utf8():
    assert decode_body("Preparação".encode("utf-8"), "application/json") == "Preparação"
    assert decode_body("Preparação".encode("utf-8"), None) == "Preparação"


def test_an_unknown_charset_falls_back_to_utf8_instead_of_raising():
    assert decode_body("ação".encode("utf-8"), "text/json; charset=klingon") == "ação"


def test_the_charset_is_found_however_it_is_written():
    assert declared_charset('text/json; charset="ISO-8859-1"') == "ISO-8859-1"
    assert declared_charset("text/json;CHARSET=utf-8; x=y") == "utf-8"
    assert declared_charset("") == "utf-8"


def test_bytes_the_charset_cannot_map_are_replaced_not_raised():
    # 0x81 is undefined in cp1252; the caller refuses U+FFFD downstream.
    assert "�" in decode_body(b"a\x81b", CP1252)


class _PageReturning:
    """A CdpPage whose browser answers ``fetch`` with a canned envelope."""

    def __init__(self, status, content_type, raw):
        self.answer = json.dumps(
            {"status": status, "contentType": content_type, "body": base64.b64encode(raw).decode()}
        )

    def build(self):
        page = CdpPage.__new__(CdpPage)
        page.evaluate = lambda expression: self.answer
        page._ws = type("W", (), {"gettimeout": lambda s: 1, "settimeout": lambda s, t: None})()
        return page


def test_fetch_json_honours_the_declared_charset():
    body = json.dumps({"ReturnObject": [LABEL]}, ensure_ascii=False).encode("cp1252")
    page = _PageReturning(200, CP1252, body).build()
    assert page.fetch_json("/x") == {"ReturnObject": [LABEL]}
