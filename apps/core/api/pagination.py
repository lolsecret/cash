from urllib.parse import urlparse

from rest_framework import pagination
from rest_framework.response import Response


def without_domain(url):
    """Remove scheme and domain"""
    if url:
        parsed = urlparse(url)
        return parsed.path + '?' + parsed.query
    return None


class DefaultPagination(pagination.PageNumberPagination):
    page_size = 1000

    def get_paginated_response(self, data):
        return Response({
            'page_number': self.page.number,
            'per_page': self.page.paginator.per_page,
            'count': self.page.paginator.count,
            'next': without_domain(self.get_next_link()),
            'previous': without_domain(self.get_previous_link()),
            'results': data,
        })


class CustomPagination(DefaultPagination):
    page_size = 20
