"""发布清单拉取与校验。仅允许 HTTPS + 可信主机(防 SSRF)。"""
from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

import requests

ALLOWED_HOSTS = {
    'raw.githubusercontent.com', 'github.com',
    'objects.githubusercontent.com', 'ghcr.io',
}


class ManifestError(Exception):
    pass


def validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != 'https':
        raise ManifestError(f'only HTTPS allowed: {url}')
    host = parsed.hostname or ''
    if host not in ALLOWED_HOSTS and not any(host.endswith('.' + h) for h in ALLOWED_HOSTS):
        raise ManifestError(f'untrusted host: {host}')


@dataclass
class Manifest:
    latest_version: str
    published_at: str = ''
    release_notes_md: str = ''
    min_upgradable_from: str = ''
    docker: dict = field(default_factory=dict)
    native: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)


def fetch_manifest(url: str, *, timeout: int = 10) -> Manifest:
    validate_url(url)
    try:
        resp = requests.get(url, timeout=timeout, headers={'Accept': 'application/json'})
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise ManifestError(f'failed to fetch manifest: {exc}') from exc
    if not isinstance(data, dict) or 'latest_version' not in data:
        raise ManifestError('invalid manifest: missing latest_version')
    return Manifest(
        latest_version=str(data['latest_version']),
        published_at=str(data.get('published_at', '')),
        release_notes_md=str(data.get('release_notes_md', '')),
        min_upgradable_from=str(data.get('min_upgradable_from', '')),
        docker=data.get('docker') or {},
        native=data.get('native') or {},
        raw=data,
    )
