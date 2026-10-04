from __future__ import annotations

import re

_WHITESPACE_RE = re.compile(r"\s+")
_CYRILLIC_RE = re.compile(r"[а-яА-ЯёЁ]")
_LATIN_RE = re.compile(r"[a-zA-Z]")

_CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)
_CWE_RE = re.compile(r"\bCWE-\d{1,4}\b", re.IGNORECASE)
_CVSS_RE = re.compile(r"\bCVSS[:\s]*[0-9]\.[0-9]\b", re.IGNORECASE)


def clean_text(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text or "").strip()


def detect_language(text: str) -> str:
    sample = (text or "")[:2000]
    cyr = len(_CYRILLIC_RE.findall(sample))
    lat = len(_LATIN_RE.findall(sample))
    if cyr == 0 and lat == 0:
        return "unknown"
    return "ru" if cyr >= lat else "en"


def extract_security_tags(text: str) -> list[str]:
    if not text:
        return []
    tags: set[str] = set()
    tags.update(m.upper() for m in _CVE_RE.findall(text))
    tags.update(m.upper() for m in _CWE_RE.findall(text))
    tags.update(m.upper().replace(" ", "") for m in _CVSS_RE.findall(text))
    return sorted(tags)
