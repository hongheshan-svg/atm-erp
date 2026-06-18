import json
from unittest import mock
from django.test import SimpleTestCase
from apps.core.manifest_client import validate_url, fetch_manifest, ManifestError

SAMPLE = {
    "latest_version": "0.3.0", "published_at": "2026-07-01T00:00:00Z",
    "release_notes_md": "## 0.3.0", "min_upgradable_from": "0.2.0",
    "docker": {"registry": "ghcr.io", "owner": "hongheshan-svg", "image_tag": "0.3.0",
               "digests": {"backend": "sha256:a", "frontend": "sha256:b"}},
    "native": {"tarball_url": "https://github.com/hongheshan-svg/atm-erp-release/releases/download/v0.3.0/erp-0.3.0.tar.gz",
               "sha256": "deadbeef"},
}


class ValidateUrlTest(SimpleTestCase):
    def test_rejects_non_https(self):
        with self.assertRaises(ManifestError):
            validate_url('http://raw.githubusercontent.com/x')

    def test_rejects_untrusted_host(self):
        with self.assertRaises(ManifestError):
            validate_url('https://evil.example.com/manifest.json')

    def test_allows_trusted(self):
        validate_url('https://raw.githubusercontent.com/hongheshan-svg/atm-erp-release/main/manifest.json')


class FetchManifestTest(SimpleTestCase):
    def test_parses(self):
        resp = mock.Mock(status_code=200, text=json.dumps(SAMPLE))
        resp.json.return_value = SAMPLE
        resp.raise_for_status = mock.Mock()
        with mock.patch('apps.core.manifest_client.requests.get', return_value=resp) as g:
            m = fetch_manifest('https://raw.githubusercontent.com/x/y/main/manifest.json')
        g.assert_called_once()
        self.assertEqual(m.latest_version, '0.3.0')
        self.assertEqual(m.min_upgradable_from, '0.2.0')
        self.assertEqual(m.docker['image_tag'], '0.3.0')
        self.assertEqual(m.native['sha256'], 'deadbeef')

    def test_rejects_redirect(self):
        """3xx 响应必须抛出 ManifestError，防止 SSRF 白名单绕过。"""
        resp = mock.Mock(status_code=302, headers={'Location': 'https://evil.example.com/x'})
        resp.raise_for_status = mock.Mock()  # raise_for_status does NOT raise on 3xx
        with mock.patch('apps.core.manifest_client.requests.get', return_value=resp) as g:
            with self.assertRaises(ManifestError):
                fetch_manifest('https://raw.githubusercontent.com/x/y/main/manifest.json')
        # ensure redirects were disabled
        self.assertEqual(g.call_args.kwargs.get('allow_redirects'), False)
