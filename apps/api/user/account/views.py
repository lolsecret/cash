import logging
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.exceptions import IsNotClient
from apps.accounts.models import Profile
from apps.accounts.serializers import AccountInfoSerializer
from apps.api.permissions import IsProfileAuthenticated

from apps.api.user.account.serializers import ProfileDataSerializer
from apps.api.user.auth.views import CREDIT_APPROVED_STATUSES
from apps.credits.models import CreditApplication

logger = logging.getLogger(__name__)


class AccountInfo(APIView):
    """
    Информация по клиенту
    """
    permission_classes = (IsProfileAuthenticated,)

    def get(self, request):  # noqa
        # service = AccountService()
        # data = service.info(user=request.user)
        #
        # if not data:
        #     return Response(
        #         {"status": "ERROR", "message": "Ошибка запроса"},
        #         status=status.HTTP_400_BAD_REQUEST
        #     )
        account: Profile = request.user
        serializer = AccountInfoSerializer(account)
        return Response(serializer.data)


class ProfileDataView(APIView):
    """
    Информация для профиля в личном кабинете
    """

    permission_classes = (IsProfileAuthenticated,)

    @property
    def record(self):
        profile: Profile = self.request.user
        credit_qs = CreditApplication.objects.filter(borrower=profile.person, status__in=CREDIT_APPROVED_STATUSES)
        if not credit_qs.exists():
            logger.error("У profile=%s, iin=%s не найден кредит, не является клиентом", profile, profile.person.iin)
            raise IsNotClient

        # Находим последнюю активную заявку
        credit: CreditApplication = credit_qs.order_by('-pk').first()
        return credit.borrower_data

    def get(self, request, *args, **kwargs):
        serializer = ProfileDataSerializer(instance=self.record)
        return Response(serializer.data, status=status.HTTP_200_OK)
