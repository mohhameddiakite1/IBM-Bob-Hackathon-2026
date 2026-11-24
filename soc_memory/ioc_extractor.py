"""IOC extractor — regex-based extraction of indicators of compromise from free text."""

from __future__ import annotations

import re

from soc_memory.models import IOC, IOCType

# ── Compiled regex patterns ────────────────────────────────────────────────────

# IPv4: four dotted octets (0-255 each); must not be part of a longer number
_RE_IPV4 = re.compile(
    r"(?<![.\d])"
    r"(?:(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]\d|\d)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]\d|\d)"
    r"(?![.\d])"
)

# Domain: at least one label + a known or plausible TLD (2-6 chars); not a plain IP
_RE_DOMAIN = re.compile(
    r"(?<![/@])"                           # not part of a URL path / user@
    r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)"
    r"+[a-zA-Z]{2,6}\b"
)

# URL: http(s):// or ftp:// prefix; trailing punctuation (.,;:!?) is stripped
_RE_URL = re.compile(
    r"https?://[^\s\"'<>]+(?<![.,;:!?])"
    r"|ftp://[^\s\"'<>]+(?<![.,;:!?])"
)

# MD5: exactly 32 hex chars (word-boundary guarded)
_RE_MD5 = re.compile(r"\b[0-9a-fA-F]{32}\b")

# SHA-1: exactly 40 hex chars
_RE_SHA1 = re.compile(r"\b[0-9a-fA-F]{40}\b")

# SHA-256: exactly 64 hex chars
_RE_SHA256 = re.compile(r"\b[0-9a-fA-F]{64}\b")


def extract_iocs(text: str) -> list[IOC]:
    """Extract IOCs from *text* using regex patterns.

    Returns a deduplicated list of :class:`~soc_memory.models.IOC` objects.
    Extraction order: SHA-256 → SHA-1 → MD5 (hashes first to prevent their
    hex strings being mis-matched as parts of domains or IPs), then URLs
    (before bare domains so the full URL is captured), domains, IPv4s.
    """
    seen: set[str] = set()
    results: list[IOC] = []

    def _add(ioc_type: IOCType, value: str) -> None:
        key = f"{ioc_type}:{value.lower()}"
        if key not in seen:
            seen.add(key)
            results.append(IOC(type=ioc_type, value=value))

    # Collect URL spans so we can suppress domain/IP matches inside them
    url_spans: list[tuple[int, int]] = []
    for m in _RE_URL.finditer(text):
        url_spans.append(m.span())
        _add(IOCType.url, m.group())

    def _in_url(start: int, end: int) -> bool:
        return any(us <= start and end <= ue for us, ue in url_spans)

    # Hashes — longest first to avoid subset collisions
    for m in _RE_SHA256.finditer(text):
        _add(IOCType.sha256, m.group())
    # Build sets of already-matched hash chars to skip sub-matches
    sha256_values = {ioc.value.lower() for ioc in results if ioc.type == IOCType.sha256}

    for m in _RE_SHA1.finditer(text):
        # Skip if this 40-char string is a prefix of a known SHA-256
        if any(s.startswith(m.group().lower()) for s in sha256_values):
            continue
        _add(IOCType.sha1, m.group())

    sha1_values = {ioc.value.lower() for ioc in results if ioc.type == IOCType.sha1}

    for m in _RE_MD5.finditer(text):
        val = m.group().lower()
        if any(s.startswith(val) for s in sha256_values | sha1_values):
            continue
        _add(IOCType.md5, val)

    # Domains (skip spans that are inside a URL already captured)
    for m in _RE_DOMAIN.finditer(text):
        if not _in_url(m.start(), m.end()):
            _add(IOCType.domain, m.group().lower())

    # IPv4s (skip spans inside URLs)
    for m in _RE_IPV4.finditer(text):
        if not _in_url(m.start(), m.end()):
            _add(IOCType.ipv4, m.group())

    return results
