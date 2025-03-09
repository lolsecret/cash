from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from apps.core.models import Bank, CreditIssuancePlan, Document, FAQ
from ..views import PublicAPIMixin

from . import serializers


class BankView(ListAPIView):
    permission_classes = (IsAuthenticated,)
    queryset = Bank.objects.all()
    serializer_class = serializers.BankSerializer


class IssuancePlanView(ListAPIView):
    permission_classes = (IsAuthenticated,)
    queryset = CreditIssuancePlan.objects.all()
    serializer_class = serializers.CreditIssuancePlanSerializer


class DocumentListView(PublicAPIMixin, ListAPIView):
    """
    Документы для отображения на сайте
    """

    serializer_class = serializers.DocumentListSerializer
    queryset = Document.objects.all()
    pagination_class = None


class FAQListView(PublicAPIMixin, ListAPIView):
    """
    FAQ для отображения на сайте
    """

    serializer_class = serializers.FAQListSerializer
    queryset = FAQ.objects.all()
    pagination_class = None
