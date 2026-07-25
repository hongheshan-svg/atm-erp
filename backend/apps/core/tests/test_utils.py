from unittest.mock import patch

from django.test import SimpleTestCase

from apps.core.utils import generate_code


class GenerateCodeTest(SimpleTestCase):
    @patch('random.choices', return_value=['0', '0'])
    @patch('time.time', return_value=1_784_987_482.836)
    @patch('time.time_ns', return_value=1_784_987_482_836_000_000)
    def test_codes_remain_unique_with_same_clock_and_random_suffix(self, _time_ns, _time, _choices):
        first = generate_code('AM')
        second = generate_code('AM')

        self.assertNotEqual(first, second)
