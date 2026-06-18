from django.test import SimpleTestCase
from apps.core.version import compare_versions, get_app_version, get_deploy_mode


class CompareVersionsTest(SimpleTestCase):
    def test_basic_ordering(self):
        self.assertEqual(compare_versions('0.1.0', '0.2.0'), -1)
        self.assertEqual(compare_versions('0.2.0', '0.2.0'), 0)
        self.assertEqual(compare_versions('1.0.0', '0.9.9'), 1)

    def test_strips_leading_v(self):
        self.assertEqual(compare_versions('v0.2.0', '0.2.0'), 0)

    def test_uneven_segments(self):
        self.assertEqual(compare_versions('0.2', '0.2.0'), 0)
        self.assertEqual(compare_versions('0.2.1', '0.2'), 1)

    def test_env_defaults(self):
        # 未设置 env 时有稳妥默认值
        self.assertIsInstance(get_app_version(), str)
        self.assertIn(get_deploy_mode(), ('docker', 'native', 'unknown'))
