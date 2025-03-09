from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from apps.api.permissions import IsProfile
from apps.api.scoring.views import LeadUUIDLookupMixin
from apps.credits.models import CreditApplication, Lead
from apps.flow.api.serializers import PKBBiometricSerializer
from apps.flow.api.services import pkb_biometry_check


class PKBBiometricUploadAPIView(LeadUUIDLookupMixin, GenericAPIView):
    serializer_class = PKBBiometricSerializer
    permission_classes = (IsProfile,)
    http_method_names = ['post']
    parser_classes = (MultiPartParser,)

    @swagger_auto_schema(
        request_body=PKBBiometricSerializer
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        credit = self.get_object().credit
        personal_record = request.user.personal_record

        if not personal_record or not personal_record.document_photo:
            return Response(
                {"detail": "Нет доступного документа для personal_record."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        biometry_photos_instance = credit.init_biometry_photos()
        biometry_photos_instance.borrower_photo = serializer.validated_data['borrower_photo']
        biometry_photos_instance.save(update_fields=["borrower_photo"])

        # Вызываем функцию проверки биометрии
        biometry_photos_instance = pkb_biometry_check(
            instance=credit,
            personal_record=personal_record
        )

        serializer_data = self.get_serializer(biometry_photos_instance)
        return Response(serializer_data.data)
