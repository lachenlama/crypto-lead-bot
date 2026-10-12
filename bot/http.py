"""Shared httpx client factory."""
import httpx

from .config import HTTP_TIMEOUT, USER_AGENT


def client() -> httpx.Client:
    return httpx.Client(
        timeout=HTTP_TIMEOUT,
        headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
        follow_redirects=True,
    )
