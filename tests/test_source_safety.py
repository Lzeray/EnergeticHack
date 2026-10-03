import socket

import pytest

from app.sources.safety import UnsafeURLError, validate_outbound_url


def _fake_getaddrinfo(ip: str):
    def _impl(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]

    return _impl


def test_rejects_non_http_scheme():
    with pytest.raises(UnsafeURLError, match="scheme"):
        validate_outbound_url("file:///etc/passwd")


def test_rejects_url_with_no_hostname():
    with pytest.raises(UnsafeURLError, match="hostname"):
        validate_outbound_url("http://")


def test_rejects_blocked_hostname_without_dns(monkeypatch):
    def _fail(*a, **k):
        raise AssertionError("should not need DNS for a blocklisted hostname")

    monkeypatch.setattr(socket, "getaddrinfo", _fail)
    with pytest.raises(UnsafeURLError, match="Blocked hostname"):
        validate_outbound_url("http://localhost/admin")


def test_rejects_loopback_address(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo("127.0.0.1"))
    with pytest.raises(UnsafeURLError, match="non-public"):
        validate_outbound_url("http://example.com/")


def test_rejects_private_lan_address(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo("10.0.0.5"))
    with pytest.raises(UnsafeURLError, match="non-public"):
        validate_outbound_url("http://internal.example.com/")


def test_rejects_cloud_metadata_address(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo("169.254.169.254"))
    with pytest.raises(UnsafeURLError, match="non-public"):
        validate_outbound_url("http://metadata-proxy.example.com/")


def test_allows_public_address(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo("93.184.216.34"))
    validate_outbound_url("http://example.com/feed.xml")  # should not raise


def test_rejects_dns_resolution_failure(monkeypatch):
    def _fail(*a, **k):
        raise socket.gaierror("name or service not known")

    monkeypatch.setattr(socket, "getaddrinfo", _fail)
    with pytest.raises(UnsafeURLError, match="Could not resolve"):
        validate_outbound_url("http://does-not-exist.invalid/")
