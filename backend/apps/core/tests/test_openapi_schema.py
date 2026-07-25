from django.test import SimpleTestCase
from drf_spectacular.drainage import GENERATOR_STATS
from drf_spectacular.generators import SchemaGenerator


class OpenAPISchemaTest(SimpleTestCase):
    def test_schema_generation_has_no_warnings_or_errors(self):
        GENERATOR_STATS.reset()

        schema = SchemaGenerator().get_schema(request=None, public=True)

        self.assertTrue(schema['paths'])
        self.assertFalse(
            GENERATOR_STATS,
            msg=(f'OpenAPI warnings={list(GENERATOR_STATS._warn_cache)} errors={list(GENERATOR_STATS._error_cache)}'),
        )
