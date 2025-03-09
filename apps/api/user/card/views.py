from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import BankAccount, BankCard
from apps.api.permissions import IsProfileAuthenticated
from apps.api.user.card.serializers import BankCardSerializer, BankAccountSerializer


class BankAccountListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsProfileAuthenticated]
    serializer_class = BankAccountSerializer

    def get_queryset(self):
        personal_record = self.request.user.personal_record
        if not personal_record:
            raise PermissionDenied("Регистрационные данные отсутствуют.")
        return BankAccount.objects.filter(record=personal_record)

    def perform_create(self, serializer):
        personal_record = self.request.user.personal_record
        if not personal_record:
            raise PermissionDenied("Регистрационные данные отсутствуют.")
        serializer.save(record=personal_record)


class BankAccountDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsProfileAuthenticated]
    serializer_class = BankAccountSerializer

    def get_queryset(self):
        personal_record = self.request.user.personal_record
        if not personal_record:
            raise PermissionDenied("Регистрационные данные отсутствуют.")
        return BankAccount.objects.filter(record=personal_record)


class BankCardListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsProfileAuthenticated]
    serializer_class = BankCardSerializer

    def get_queryset(self):
        personal_record = self.request.user.personal_record
        if not personal_record:
            raise PermissionDenied("Регистрационные данные отсутствуют.")
        return BankCard.objects.filter(record=personal_record)

    def perform_create(self, serializer):
        personal_record = self.request.user.personal_record
        if not personal_record:
            raise PermissionDenied("Регистрационные данные отсутствуют.")
        serializer.save(record=personal_record)


class BankCardDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsProfileAuthenticated]
    serializer_class = BankCardSerializer

    def get_queryset(self):
        personal_record = self.request.user.personal_record
        if not personal_record:
            raise PermissionDenied("Регистрационные данные отсутствуют.")
        return BankCard.objects.filter(record=personal_record)
