from __future__ import annotations

import calendar
import datetime as dt
import re
import time

from bs4 import BeautifulSoup

_WHITESPACE_RE = re.compile(r"[ \t ]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")


def strip_html(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text("\n")
    text = _WHITESPACE_RE.sub(" ", text)
    text = _BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()


def struct_time_to_dt(struct: time.struct_time | None) -> dt.datetime | None:
    if struct is None:
        return None
    return dt.datetime.fromtimestamp(calendar.timegm(struct), tz=dt.timezone.utc)


def absolute_url(base_url: str, href: str) -> str:
    from urllib.parse import urljoin

    return urljoin(base_url, href)
