"""Database-backed global search views."""

from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


class GlobalSearchViewSet(viewsets.ViewSet):
    """Search the primary business entities without an external search service."""

    permission_classes = [IsAuthenticated]
    search_types = {'items', 'customers', 'suppliers', 'projects', 'tasks'}

    @action(detail=False, methods=['get'])
    def search(self, request):
        query = request.query_params.get('q', '').strip()
        search_type = request.query_params.get('type')
        limit = self._parse_limit(request.query_params.get('limit'), default=10)

        if not query:
            return Response({'error': 'Search query is required'}, status=status.HTTP_400_BAD_REQUEST)
        if search_type and search_type not in self.search_types:
            return Response({'error': f'Invalid type: {search_type}'}, status=status.HTTP_400_BAD_REQUEST)

        types_to_search = {search_type} if search_type else self.search_types
        return Response(self._database_search(query, types_to_search, limit))

    @action(detail=False, methods=['get'])
    def suggest(self, request):
        query = request.query_params.get('q', '').strip()
        search_type = request.query_params.get('type', 'items')
        limit = self._parse_limit(request.query_params.get('limit'), default=5)

        if search_type not in self.search_types:
            return Response({'error': f'Invalid type: {search_type}'}, status=status.HTTP_400_BAD_REQUEST)
        if len(query) < 2:
            return Response({'suggestions': []})

        return Response({'suggestions': self._database_suggestions(query, search_type, limit)})

    @staticmethod
    def _parse_limit(raw_limit, default):
        try:
            return min(max(int(raw_limit or default), 1), 100)
        except (TypeError, ValueError):
            return default

    def _database_search(self, query, search_types, limit):
        results = {}
        for search_type in sorted(search_types):
            queryset = self._database_queryset(query, search_type)
            hits = [self._format_database_hit(obj, search_type) for obj in queryset[:limit]]
            results[search_type] = {'total': queryset.count(), 'hits': hits}
        return {
            'query': query,
            'results': results,
            'total_hits': sum(result['total'] for result in results.values()),
        }

    def _database_suggestions(self, query, search_type, limit):
        queryset = self._database_queryset(query, search_type)
        return [
            {
                'id': obj.id,
                'text': obj.name,
                'type': search_type,
                'meta': getattr(obj, 'code', None) or getattr(obj, 'sku', None),
            }
            for obj in queryset[:limit]
        ]

    @staticmethod
    def _database_queryset(query, search_type):
        if search_type == 'items':
            from apps.masterdata.models import Item

            return Item.objects.filter(
                Q(sku__icontains=query)
                | Q(name__icontains=query)
                | Q(specification__icontains=query)
                | Q(barcode__icontains=query)
            ).order_by('name')
        if search_type == 'customers':
            from apps.masterdata.models import Customer

            return Customer.objects.filter(
                Q(code__icontains=query)
                | Q(name__icontains=query)
                | Q(contact_person__icontains=query)
                | Q(phone__icontains=query)
                | Q(email__icontains=query)
            ).order_by('name')
        if search_type == 'suppliers':
            from apps.masterdata.models import Supplier

            return Supplier.objects.filter(
                Q(code__icontains=query)
                | Q(name__icontains=query)
                | Q(contact_person__icontains=query)
                | Q(phone__icontains=query)
                | Q(email__icontains=query)
            ).order_by('name')
        if search_type == 'projects':
            from apps.projects.models import Project

            return Project.objects.filter(
                Q(code__icontains=query) | Q(name__icontains=query) | Q(customer__name__icontains=query)
            ).order_by('name')

        from apps.projects.models import ProjectTask

        return ProjectTask.objects.filter(
            Q(code__icontains=query)
            | Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(project__name__icontains=query)
        ).order_by('name')

    @staticmethod
    def _format_database_hit(obj, search_type):
        result = {'id': obj.id, 'score': None, 'type': search_type}
        if search_type == 'items':
            result.update({'sku': obj.sku, 'name': obj.name, 'specification': obj.specification})
        elif search_type in {'customers', 'suppliers'}:
            result.update(
                {
                    'code': obj.code,
                    'name': obj.name,
                    'contact_person': obj.contact_person,
                    'phone': obj.phone,
                }
            )
        elif search_type == 'projects':
            result.update({'code': obj.code, 'name': obj.name, 'status': obj.status})
        else:
            result.update({'name': obj.name, 'status': obj.status})
        return result
