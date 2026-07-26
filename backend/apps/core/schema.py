"""OpenAPI schema policies shared by the ERP APIs."""

import re
from collections.abc import MutableMapping

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.hooks import postprocess_schema_enum_id_removal
from drf_spectacular.openapi import AutoSchema
from drf_spectacular.plumbing import (
    ResolvedComponent,
    build_serializer_context,
    is_jsonschema_compliant,
    list_hash,
    safe_ref,
)
from drf_spectacular.settings import spectacular_settings
from drf_spectacular.types import OpenApiTypes
from inflection import camelize
from rest_framework.generics import GenericAPIView
from rest_framework.views import APIView


class ERPAutoSchema(AutoSchema):
    """Document free-form reporting endpoints without dropping them from the schema."""

    def _get_serializer(self):
        view = self.view
        context = build_serializer_context(view)

        try:
            if isinstance(view, GenericAPIView):
                if view.__class__.get_serializer == GenericAPIView.get_serializer:
                    return view.get_serializer_class()(context=context)
                return view.get_serializer(context=context)
            if isinstance(view, APIView):
                serializer_class = getattr(view, 'serializer_class', None)
                if serializer_class:
                    return serializer_class
                if callable(getattr(view, 'get_serializer_class', None)):
                    return view.get_serializer_class()(context=context)
                if callable(getattr(view, 'get_serializer', None)):
                    return view.get_serializer(context=context)
        except (AttributeError, TypeError):
            # ViewSet-based dashboards intentionally return computed dictionaries and
            # inherit PermissionMixin.get_serializer without a GenericAPIView parent.
            pass

        return OpenApiTypes.OBJECT


class CustomerPortalJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    """Expose the dedicated customer-portal JWT as a bearer security scheme."""

    target_class = 'apps.sales.after_sales_service.CustomerPortalJWTAuthentication'
    name = 'customerPortalBearerAuth'

    def get_security_definition(self, auto_schema):
        return {'type': 'http', 'scheme': 'bearer', 'bearerFormat': 'JWT'}


class SupplierPortalAuthenticationScheme(OpenApiAuthenticationExtension):
    """Expose the signed supplier-portal session as its own auth scheme."""

    target_class = 'apps.purchase.supplier_portal.SupplierPortalAuthentication'
    name = 'supplierPortalAuth'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'apiKey',
            'in': 'header',
            'name': 'Authorization',
            'description': 'Use the `Supplier <signed-token>` authorization scheme.',
        }


def postprocess_contextual_enums(result, generator, **kwargs):
    """Name enums by component, field, and content instead of ambiguous field names.

    ERP modules legitimately define many unrelated ``status`` and ``type`` choice
    sets. Contextual names keep generated clients stable and avoid hash-only
    collision names while preserving every distinct choice set.
    """

    def iter_property_containers(schema, component_name=None):
        if not component_name:
            for current_name, current_schema in schema.items():
                if spectacular_settings.COMPONENT_SPLIT_PATCH:
                    current_name = re.sub(r'^Patched(.+)', r'\1', current_name)
                if spectacular_settings.COMPONENT_SPLIT_REQUEST:
                    current_name = re.sub(r'(.+)Request$', r'\1', current_name)
                yield from iter_property_containers(current_schema, current_name)
        elif isinstance(schema, list):
            for item in schema:
                yield from iter_property_containers(item, component_name)
        elif isinstance(schema, dict):
            if schema.get('properties'):
                yield component_name, schema['properties']
            yield from iter_property_containers(schema.get('oneOf', []), component_name)
            yield from iter_property_containers(schema.get('allOf', []), component_name)
            yield from iter_property_containers(schema.get('anyOf', []), component_name)

    def enum_hash(schema):
        if 'x-spec-enum-id' in schema:
            return schema['x-spec-enum-id']
        return list_hash([(value, value) for value in schema['enum'] if value not in ('', None)])

    def register_enum(name, schema):
        component = ResolvedComponent(
            name=name,
            type=ResolvedComponent.SCHEMA,
            schema=schema,
            object=name,
        )
        generator.registry.register_on_missing(component)
        return component

    schemas = result.get('components', {}).get('schemas', {})
    suffix = spectacular_settings.ENUM_SUFFIX

    for component_name, properties in iter_property_containers(schemas):
        for property_name, outer_schema in list(properties.items()):
            is_array = outer_schema.get('type') == 'array'
            property_schema = outer_schema.get('items') if is_array else outer_schema
            if not isinstance(property_schema, MutableMapping) or 'enum' not in property_schema:
                continue

            original_values = property_schema['enum']
            property_schema['enum'] = [value for value in original_values if value not in ('', None)]
            digest = enum_hash(property_schema)[:8]
            enum_name = f'{camelize(component_name)}{camelize(property_name)}{digest}{suffix}'

            enum_schema = {key: value for key, value in property_schema.items() if key in ('type', 'enum')}
            remaining_schema = {
                key: value for key, value in property_schema.items() if key not in ('type', 'enum', 'x-spec-enum-id')
            }

            if spectacular_settings.ENUM_GENERATE_CHOICE_DESCRIPTION:
                description = remaining_schema.get('description', '')
                if description.startswith('*'):
                    enum_schema['description'] = remaining_schema.pop('description')
                elif '\n\n*' in description:
                    _, _, choice_description = description.partition('\n\n*')
                    enum_schema['description'] = f'*{choice_description}'

            components = [register_enum(enum_name, enum_schema)]
            if spectacular_settings.ENUM_ADD_EXPLICIT_BLANK_NULL_CHOICE:
                if '' in original_values:
                    components.append(register_enum(f'Blank{suffix}', {'enum': ['']}))
                if None in original_values:
                    null_schema = {'type': 'null'} if is_jsonschema_compliant() else {'enum': [None]}
                    components.append(register_enum(f'Null{suffix}', null_schema))

            if is_jsonschema_compliant() and isinstance(enum_schema['type'], list):
                enum_schema['type'] = next(value for value in enum_schema['type'] if value != 'null')

            if len(components) == 1:
                remaining_schema.update(components[0].ref)
            else:
                remaining_schema.update({'oneOf': [component.ref for component in components]})

            if is_array:
                outer_schema['items'] = safe_ref(remaining_schema)
            else:
                properties[property_name] = safe_ref(remaining_schema)

    result['components'] = generator.registry.build(spectacular_settings.APPEND_COMPONENTS)
    postprocess_schema_enum_id_removal(result, generator)
    return result
