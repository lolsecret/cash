from typing import Dict

from django.http.response import HttpResponse
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from . import serializers


class PublicAPIMixin:
    permission_classes = [AllowAny]


class TextChoiceListView(ListAPIView):
    serializer_class = serializers.TextChoiceSerializer
    pagination_class = None
    choices: Dict = {}

    def list(self, request, **kwargs):
        data = [
            {"const_name": key, "name": value} for key, value in self.choices.items()
        ]
        serializer = self.get_serializer(data, many=True)
        return Response(serializer.data)
