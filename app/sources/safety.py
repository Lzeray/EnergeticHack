from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

_ALLOWED_SCHEMES = {"http", "https"}
_BLOCKED_HOSTNAMES = {"localhost", "metadata.google.internal"}


class UnsafeURLError(ValueError):
    """Raised when a URL a source adapter was about to fetch resolves to a
    non-public address (loopback, private LAN, link-local/cloud metadata,
    etc.) — refuses the request instead of letting a malicious or careless
    source config turn the digest service into an SSRF proxy into the
    operator's own network."""


def validate_outbound_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise UnsafeURLError(f"Disallowed URL scheme: {parsed.scheme!r} (only http/https are fetched)")

    hostname = parsed.hostname
    if not hostname:
        raise UnsafeURLError(f"URL has no hostname: {url!r}")
    if hostname.lower() in _BLOCKED_HOSTNAMES:
        raise UnsafeURLError(f"Blocked hostname: {hostname}")

    try:
        resolved = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"Could not resolve host {hostname!r}: {exc}") from exc

    for family, _type, _proto, _canon, sockaddr in resolved:
        ip = ipaddress.ip_address(sockaddr[0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise UnsafeURLError(
                f"Host {hostname!r} resolves to a non-public address ({ip}); refusing to fetch it"
            )
