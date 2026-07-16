"""Shared factory for outgoing HTTP clients (TLS and proxy policy)."""

from typing import Optional
from urllib.request import getproxies

import httpx

from .config import Settings, get_settings


def create_async_http_client(
    *,
    settings: Optional[Settings] = None,
    **kwargs,
) -> httpx.AsyncClient:
    """Create an AsyncClient with the application-wide TLS and proxy policy.

    trust_env=True lets httpx honour HTTP_PROXY/HTTPS_PROXY/ALL_PROXY/NO_PROXY
    and SSL_CERT_FILE/SSL_CERT_DIR. SSL_CERT_* only apply when verify is True.
    """
    current_settings = settings or get_settings()
    return httpx.AsyncClient(
        verify=current_settings.SSL_VERIFY,
        trust_env=True,
        **kwargs,
    )


def env_proxy_configured() -> bool:
    """True if httpx would actually route outgoing traffic through a proxy.

    Mirrors httpx._utils.get_environment_proxies() without depending on its
    private API: NO_PROXY=* disables every proxy route, and only the
    http/https/all schemes create a route at all ("no" is a bypass list).
    """
    proxies = getproxies()
    no_proxy = [host.strip() for host in proxies.get("no", "").split(",")]
    if "*" in no_proxy:
        return False
    return any(proxies.get(scheme) for scheme in ("http", "https", "all"))
