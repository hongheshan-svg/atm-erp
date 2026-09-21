import unittest
from pathlib import Path

from scripts.package_release import docker_compose


class DirectComposeTests(unittest.TestCase):
    def test_release_defaults_to_verified_digest_without_build_or_host_agent(self):
        template = (Path(__file__).parents[2] / 'docker-compose.yml').read_text()
        image = 'ghcr.io/hongheshan-svg/atm-erp@sha256:' + 'a' * 64
        result = docker_compose(template, image)
        self.assertIn('${LEAN_IMAGE:-' + image + '}', result)
        self.assertNotIn('    build:', result)
        self.assertNotIn('docker.sock', result)
        self.assertIn('OTA_AGENT_TOKEN: ${LEAN_OTA_AGENT_TOKEN:-}', result)
        for bad in ('image:latest', 'ghcr.io/hongheshan-svg/atm-erp:latest'):
            with self.assertRaises(ValueError):
                docker_compose(template, bad)
        with self.assertRaises(ValueError):
            docker_compose('image: unknown', image)
