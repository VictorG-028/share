"""
Turning the bytes of an HTTP answer into text, the way the *header* says.

The SSG service layer answers ``Content-Type: text/json; charset=Windows-1252``
(measured 2026-10-02) while the page itself is UTF-8. ``fetch``'s own
``Response.text()`` ignores the header and always reads UTF-8, so every ``ç``
(byte ``E7``) became ``U+FFFD`` before it reached the catalog -- and a catalog
label with a replacement character can never match the row the site shows.
XHR/jQuery, which the site uses, honours the header; this does the same.

Pure on purpose: no browser, so it is plain-pytest tested.
"""

from __future__ import annotations

import codecs
import re

_CHARSET = re.compile(r"charset\s*=\s*[\"']?([^\s;\"']+)", re.IGNORECASE)


def declared_charset(content_type: str | None) -> str:
    """The charset a ``Content-Type`` declares, or ``utf-8`` when it says none."""
    match = _CHARSET.search(content_type or "")
    return match.group(1) if match else "utf-8"


def decode_body(raw: bytes, content_type: str | None) -> str:
    """
    ``raw`` decoded with the charset ``content_type`` declares.

    An absent or unknown charset reads as UTF-8 (what ``fetch`` did before).
    Bytes the declared charset cannot map are replaced, not raised: the caller
    refuses a result carrying ``U+FFFD`` (``osi_catalog.entry.REPLACEMENT_CHAR``)
    instead of storing it.
    """
    charset = declared_charset(content_type)
    try:
        codecs.lookup(charset)
    except LookupError:
        charset = "utf-8"
    return raw.decode(charset, errors="replace")
