import logging

from constance import config
from django.utils.translation import gettext_lazy as _

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.generics import CreateAPIView, GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.credits.models import (
    Lead,
    CreditApplication,
)
from apps.notifications.services import send_otp
from apps.flow.services import Flow

from . import serializers
from ..permissions import IsProfileAuthenticated, IsProfile

logger = logging.getLogger(__name__)


class LeadUUIDLookupMixin:
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"

    queryset = Lead.objects.all()


class CreditUUIDLookupMixin:
    lookup_field = "lead_id"
    lookup_url_kwarg = "uuid"

    queryset = CreditApplication.objects.all()


class LeadApplyAPIView(LeadUUIDLookupMixin, CreateAPIView):
    serializer_class = serializers.CreditFastCreateAPIViewSerializer
    queryset = CreditApplication.objects.all()
    permission_classes = (IsProfile,)



# class LeadApplyAPIView(LeadUUIDLookupMixin, CreateAPIView):
#     serializer_class = serializers.CreditApplyAPIViewSerializer
#     queryset = CreditApplication.objects.all()
#     permission_classes = (AllowAny,)
#     authentication_classes = []
#
#     def post(self, request, *args, **kwargs):
#         if config.LANDING_PRODUCT and 'product' not in request.data:
#             request.data['product'] = config.LANDING_PRODUCT
#
#         return super().post(request, *args, **kwargs)


# class LeadViewSet(
#     # MethodMatchingViewSetMixin,
#     LeadUUIDLookupMixin,
#     ModelViewSet
# ):
#     action_serializers = {
#         "create": serializers.CreditCreateViewSerializer,
#         "send_otp": serializers.SendOTPSerializer,
#         "verify_otp": "",
#         "execute": serializers.ExecuteSerializer
#     }
#     http_method_names = ('get', 'post', 'put')
#
#     @action(["get"], detail=True)
#     def send_otp(self, request, *args, **kwargs):
#         lead = self.get_object()
#         send_otp(lead.mobile_phone)
#         return Response(self.get_serializer(lead).data)
#
#     @action(["post"], detail=True)
#     def verify_otp(self, request, *args, **kwargs):
#         lead = self.get_object()
#         serializer = self.get_serializer(lead, data=request.data)
#         serializer.is_valid(raise_exception=True)
#         lead.verify(serializer.validated_data["otp_code"])
#         return Response(serializer.data)
#
#     @action(["put"], detail=True)
#     def execute(self, request, *args, **kwargs):
#         lead = self.get_object()
#         lead.product.pipeline.run_for(lead)
#         return Response(self.get_serializer(lead).data)


# class LeadScoringView(LeadUUIDLookupMixin, GenericAPIView):
#     """
#     Запуск скоринга по ранее созданной заявке
#     """
#     queryset = Lead.objects.filter(rejected=False)
#     serializer_class = serializers.VerifyOTPSerializer
#     permission_classes = (AllowAny,)
#     http_method_names = ('post',)
#
#     def post(self, request, *args, **kwargs):
#         lead: Lead = self.get_object()
#         serializer = self.get_serializer(lead, data=request.data)
#         serializer.is_valid(raise_exception=True)
#         lead.verify(serializer.validated_data["otp_code"])
#
#         if lead.product.pipeline:
#             credit = lead.create_credit_application()
#             credit.to_check()
#             credit.save()
#
#             try:
#                 Flow(lead.product.pipeline, lead).run()
#
#             except Exception as exc:
#                 logger.error('LeadScoringView pipeline.run: %s', exc)
#                 logger.exception(exc)
#                 response = {"message": _("Произошла ошибка")}
#                 return Response(response, status=status.HTTP_400_BAD_REQUEST)
#
#         return Response(status=status.HTTP_200_OK)
