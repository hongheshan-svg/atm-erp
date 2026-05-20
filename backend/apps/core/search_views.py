"""
Global search views using Elasticsearch
"""

from django.conf import settings
from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


class GlobalSearchViewSet(viewsets.ViewSet):
    """
    Global search across all indexed models
    """

    permission_classes = [IsAuthenticated]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initialize Elasticsearch client
        es_config = settings.ELASTICSEARCH_DSL['default']
        self.es = Elasticsearch([es_config['hosts']])

    @action(detail=False, methods=['get'])
    def search(self, request):
        """
        Perform global search across all indexes

        Query params:
        - q: search query string
        - type: optional filter by type (items, customers, suppliers, projects, tasks)
        - limit: number of results per type (default: 10)
        """
        query = request.query_params.get('q', '').strip()
        search_type = request.query_params.get('type', None)
        limit = int(request.query_params.get('limit', 10))

        if not query:
            return Response({'error': 'Search query is required'}, status=status.HTTP_400_BAD_REQUEST)

        results = {}

        # Define indexes to search
        indexes_to_search = {
            'items': 'items',
            'customers': 'customers',
            'suppliers': 'suppliers',
            'projects': 'projects',
            'tasks': 'project_tasks',
        }

        # Filter by type if specified
        if search_type:
            if search_type not in indexes_to_search:
                return Response({'error': f'Invalid type: {search_type}'}, status=status.HTTP_400_BAD_REQUEST)
            indexes_to_search = {search_type: indexes_to_search[search_type]}

        # Search each index
        for key, index_name in indexes_to_search.items():
            try:
                search = Search(using=self.es, index=index_name)

                # Build multi-field query
                search = search.query('multi_match', query=query, fields=self._get_search_fields(key), fuzziness='AUTO')

                # Execute search
                response = search[0:limit].execute()

                # Format results
                results[key] = {
                    'total': response.hits.total.value,
                    'hits': [self._format_hit(hit, key) for hit in response],
                }
            except Exception as e:
                results[key] = {'error': str(e), 'total': 0, 'hits': []}

        return Response(
            {'query': query, 'results': results, 'total_hits': sum(r.get('total', 0) for r in results.values())}
        )

    @action(detail=False, methods=['get'])
    def suggest(self, request):
        """
        Get search suggestions/autocomplete

        Query params:
        - q: partial query string
        - type: filter by type
        - limit: number of suggestions (default: 5)
        """
        query = request.query_params.get('q', '').strip()
        search_type = request.query_params.get('type', 'items')
        limit = int(request.query_params.get('limit', 5))

        if not query or len(query) < 2:
            return Response({'suggestions': []})

        # Map type to index
        index_map = {
            'items': 'items',
            'customers': 'customers',
            'suppliers': 'suppliers',
            'projects': 'projects',
            'tasks': 'project_tasks',
        }

        index_name = index_map.get(search_type, 'items')

        try:
            search = Search(using=self.es, index=index_name)
            search = search.query('match_phrase_prefix', name={'query': query})

            response = search[0:limit].execute()

            suggestions = []
            for hit in response:
                suggestions.append(
                    {
                        'id': hit.meta.id,
                        'text': hit.name,
                        'type': search_type,
                        'meta': getattr(hit, 'code', None) or getattr(hit, 'sku', None),
                    }
                )

            return Response({'suggestions': suggestions})
        except Exception as e:
            return Response({'error': str(e), 'suggestions': []})

    def _get_search_fields(self, doc_type):
        """Get searchable fields for each document type"""
        field_mapping = {
            'items': ['sku^3', 'name^2', 'specification', 'barcode^3'],
            'customers': ['code^3', 'name^2', 'contact_person', 'phone', 'email'],
            'suppliers': ['code^3', 'name^2', 'contact_person', 'phone', 'email'],
            'projects': ['code^3', 'name^2', 'customer.name'],
            'tasks': ['name^2', 'description', 'project.name'],
        }
        return field_mapping.get(doc_type, ['*'])

    def _format_hit(self, hit, doc_type):
        """Format search hit for response"""
        result = {'id': hit.meta.id, 'score': hit.meta.score, 'type': doc_type}

        # Add relevant fields based on document type
        if doc_type == 'items':
            result.update(
                {
                    'sku': getattr(hit, 'sku', ''),
                    'name': getattr(hit, 'name', ''),
                    'specification': getattr(hit, 'specification', ''),
                }
            )
        elif doc_type in ['customers', 'suppliers']:
            result.update(
                {
                    'code': getattr(hit, 'code', ''),
                    'name': getattr(hit, 'name', ''),
                    'contact_person': getattr(hit, 'contact_person', ''),
                    'phone': getattr(hit, 'phone', ''),
                }
            )
        elif doc_type == 'projects':
            result.update(
                {
                    'code': getattr(hit, 'code', ''),
                    'name': getattr(hit, 'name', ''),
                    'status': getattr(hit, 'status', ''),
                }
            )
        elif doc_type == 'tasks':
            result.update(
                {
                    'name': getattr(hit, 'name', ''),
                    'status': getattr(hit, 'status', ''),
                }
            )

        return result
