from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.viewsets import ModelViewSet

from apps.core.views import TextChoiceListView

from . import BlackListReason, serializers
from .models import BlackListMember


class BlackListMemberViewSet(ModelViewSet):
    queryset = BlackListMember.objects.all()
    serializer_class = serializers.BlackListMemberSerializer
    filter_backends = [DjangoFilterBackend]
    filter_fields = ["reason"]


class BlackListReasonsListView(TextChoiceListView):
    choices = BlackListReason.as_dict()
