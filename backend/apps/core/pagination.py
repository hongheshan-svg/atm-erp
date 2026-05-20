"""
Custom pagination classes for the ERP system.
"""

from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """
    Standard pagination with configurable page size.
    Allows clients to specify page_size query parameter.
    """

    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 1000
