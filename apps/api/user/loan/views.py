import logging
from datetime import timedelta

from constance import config
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.timezone import localtime
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Q

from apps.api.permissions import IsProfileAuthenticated
from apps.accounts.models import Profile
from apps.accounts.services import AccountService
from apps.credits import CreditContractStatus, PaymentStatus, CreditStatus
from apps.credits.exceptions import CreditContractNotFound
from apps.credits.models import CreditContract, CreditApplicationPayment, Guarantor, CreditApplication
from apps.credits.services.soap_payment_service import SoapPaymentService
from apps.flow.models import StatusTrigger
from apps.notifications.services import send_otp, verify_otp
from apps.api.user.auth.serializers import ResponseSerializer
from apps.people.models import Person

from .utils import get_nearest_maturity
from . import serializers

logger = logging.getLogger(__name__)


class PaymentHistory(APIView):
    """История платежей"""
    permission_classes = (IsProfileAuthenticated,)
    serializer_class = serializers.PaymentHistorySerializer

    def get(self, request):
        user: Profile = request.user

        serializer = self.serializer_class(data=request.GET)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        service = AccountService()
        data = service.payment_history(
            user=user,
            date_from=serializer.validated_data['date_from'],
            date_to=serializer.validated_data['date_to'],
        )
        return Response(data)


class LoanPaymentSumPartialView(APIView):
    """
    Получение суммы частичного досрочного погашения.
    """
    serializer_class = serializers.LoanRepaymentSumSerializer
    permission_classes = (IsProfileAuthenticated,)

    @swagger_auto_schema(
        request_body=serializers.LoanRepaymentSumSerializer,
        responses={'200': serializers.LoanRepaymentPartialSumResponseSerializer()}
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        request_contract_number = serializer.validated_data.get('contract_number')
        service = AccountService()
        account_info = service.info(user=request.user)
        account_balance = account_info.get('account_balance')
        min_sum = float(50_000)  # и не меньше трех последующих платежей

        contracts = account_info['user_contract_info']
        for contract in contracts:  # type: dict
            if contract['contract_number'] == request_contract_number:
                current_amount_debt = contract.get('current_amount_debt')

                contract_number = contract['contract_number']
                # category = ProductCategory.ENTITY
                # for pr_cat in ProductCategory.objects.all():
                #     if contract_number.startswith(pr_cat.code):
                #         category = pr_cat.type
                #         break

                # is_individual = False
                # if category == ProductCategory.INDIVIDUAL:
                #     min_sum = current_amount_debt / 2
                #     is_payment_possible = account_balance > min_sum
                #     is_individual = True
                #
                # else:
                current_date = timezone.localdate()
                pay_count = 0
                pay_sum = 0

                for schedule in contract.get('payment_schedule'):  # type: dict
                    schedule_date = schedule.get('target_dates')
                    if schedule.get('payment_status') == "Не оплачен" and current_date < schedule_date:
                        pay_count += 1
                        pay_sum = pay_sum + schedule.get('payment', 0)

                    if pay_count == 3:
                        break

                min_sum = pay_sum if pay_sum > min_sum else min_sum
                is_payment_possible = pay_count <= 3 and account_balance > min_sum

                serializer_response = serializers.LoanRepaymentPartialSumResponseSerializer({
                    'contract_number': contract['contract_number'],
                    'current_amount_debt': current_amount_debt,
                    'payment_minimum': min_sum,
                    'possibility_of_payment': is_payment_possible,
                    'account_balance': account_balance,
                    'debt_date': timezone.localdate(),
                    'is_holiday': (True, "Погашение возможно только в рабочие дни с 9:00 до 17:00")
                })
                return Response(serializer_response.data)

        return Response({})


class LoanPaymentSumFullView(APIView):
    """
    Получение суммы полного досрочного погашения.
    """
    serializer_class = serializers.LoanRepaymentSumSerializer
    permission_classes = (IsProfileAuthenticated,)

    @swagger_auto_schema(
        request_body=serializers.LoanRepaymentSumSerializer,
        responses={'200': serializers.LoanRepaymentFullSumResponseSerializer()}
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        request_contract_number = serializer.validated_data.get('contract_number')

        current_date = timezone.localdate()
        debt_date = current_date + timedelta(days=1)
        # while check_holiday(debt_date, True)[0]:
        #     debt_date += timedelta(days=1)

        service = AccountService()
        service.get_client_info(iin='710404301101', phone='+77785737942', date_from=current_date, date_to=debt_date)
        account_info = service.info(user=request.user, date_from=current_date, date_to=debt_date)

        # info = account_info(
        #     iin=user.iin, tel_number=user.phone,
        #     prepayment_date1=timezone.localdate(),
        #     prepayment_date2=debt_date)
        contracts = account_info['user_contract_info']
        account_balance = account_info.get('account_balance')
        for contract in contracts:  # type: dict
            if contract['contract_number'] == request_contract_number:
                if serializer.validated_data.get('kaspi', True):
                    current_amount_debt = float(contract['current_amount_debt'])
                    debt_date = timezone.localdate()

                else:
                    current_amount_debt = float(contract['current_amount_debt2'])

                # category = ProductCategory.ENTITY
                # for pr_cat in ProductCategory.objects.all():
                #     if contract['contract_number'].startswith(pr_cat.code):
                #         category = pr_cat.type
                #         break

                # is_individual = False
                # if category == ProductCategory.INDIVIDUAL:
                #     is_individual = True

                possibility_of_payment = current_amount_debt <= account_balance
                serializer_response = serializers.LoanRepaymentFullSumResponseSerializer({
                    'contract_number': contract.get('contract_number'),
                    'current_amount_debt': current_amount_debt,
                    # Added to check if user has enough money to pay today.
                    # TODO: Optimize so same fields not sent multiple  times
                    'kaspi_debt': float(contract.get('current_amount_debt')),
                    'debt_date': debt_date,
                    'possibility_of_payment': possibility_of_payment,
                    'account_balance': account_balance,
                    'is_holiday': (True, "Погашение возможно только в рабочие дни с 9:00 до 17:00")
                })
                return Response(serializer_response.data)

        return Response({
            'contract_number': request_contract_number,
            'account_balance': account_balance
        }, status=status.HTTP_404_NOT_FOUND)


class CreditPaymentView(APIView):
    """
    Получение данных по договору для оплаты и оплата
    """
    def get_contract(self, iin: str, contract_number=None): # noqa
        contract_query = CreditContract.objects.filter(borrower__iin=iin)

        if contract_number:
            return contract_query.filter(contract_number=contract_number)

        contract = contract_query.first()

        if not contract:
            logger.error("У iin=%s не найден контракт", iin)
            raise CreditContractNotFound

        return contract

    def get(self, request, *args, **kwargs):
        iin = kwargs.get('iin')
        contract = self.get_contract(iin)

        soap_service = SoapPaymentService(contract)
        get_data_request = soap_service.send_check_request()
        serializer = serializers.CreditPaymentSerializer(data=get_data_request)
        serializer.is_valid(raise_exception=True)

        return Response(serializer.data)

    @swagger_auto_schema(
        request_body=serializers.CreditPaymentRequestSerializer(),
    )
    def post(self, request, *args, **kwargs):
        iin = kwargs.get('iin')
        person = get_object_or_404(Person, iin=iin)
        serializer = serializers.CreditPaymentRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        contract_query = self.get_contract(iin, serializer.data['contract_number'])
        payment = CreditApplicationPayment.objects.create(
            amount=serializer.data['amount'],
            contract_date=serializer.data['contract_date'],
            contract_number=serializer.data['contract_number'],
            person=person,
        )
        if contract_query.exists():
            payment.contract = contract_query.first()
            payment.save(update_fields=['contract'])
        payment.generate_and_save_order_id()
        payment.payment_class.create_payment()

        return Response(dict(pay_link=payment.pay_link))


class CreditContractBaseView(APIView):
    permission_classes = (IsProfileAuthenticated,)
    serializer_class = serializers.CreditContractSerializer

    def get_contract(self):
        profile: Profile = self.request.user
        contract_query = CreditContract.objects.filter(
            borrower=profile.person,
            contract_status=CreditContractStatus.CREATED,
        )

        if not contract_query.exists():
            logger.error("У profile=%s, iin=%s не найден контракт", profile, profile.person.iin)
            raise CreditContractNotFound

        return contract_query.first()


class CreditContractView(CreditContractBaseView):
    """
    Получение данных по договору
    """

    @swagger_auto_schema(
        responses={'200': serializers.CreditContractSerializer()}
    )
    def get(self, request, *args, **kwargs):
        contract = self.get_contract()
        serializer = serializers.CreditContractSerializer(contract)
        return Response(serializer.data)

    @swagger_auto_schema(
        request_body=serializers.CreditContractSerializer,
        responses={'200': serializers.CreditContractSerializer()}
    )
    def patch(self, request, *args, **kwargs):
        contract = self.get_contract()

        serializer = serializers.CreditContractSerializer(contract, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializers.CreditContractSerializer(contract).data)


class ValidateBorrowerOTPtoSign(CreditContractBaseView):
    """
     Отправка и проверка OTP, с последующим подписанием
    """
    @swagger_auto_schema(
        responses={'200': ResponseSerializer()}
    )
    def get(self, request, *args, **kwargs):
        profile: Profile = request.user
        send_otp(mobile_phone=profile.phone)

        return Response({"status": "OK"})

    @swagger_auto_schema(
        request_body=serializers.ValidateBorrowerOTPSerializer,
        responses={'200': ResponseSerializer()}
    )
    def post(self, request, *args, **kwargs):
        profile: Profile = request.user
        contract = self.get_contract()

        serializer = serializers.ValidateBorrowerOTPSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        otp = serializer.validated_data.get('otp')

        with transaction.atomic():
            verify_otp(otp, profile.phone, save=True)

            self.contract_sign_flow(contract, profile, otp=otp)

            transaction.on_commit(lambda: StatusTrigger.run(status=contract.credit.status, credit=contract.credit))

        return Response({"status": "OK"})

    def contract_sign_flow(self, contract: CreditContract, profile: Profile, otp: str):

        # Подпись заемщиком
        contract.credit.to_issuance(localtime().date(), profile, otp)
        contract.credit.save()
        return


class ProfileCreditContractsView(APIView):
    """
    Получение данных по договорам
    """

    permission_classes = (IsProfileAuthenticated,)
    serializer_class = serializers.CreditContractSerializer
    http_method_names = ('get',)

    def get_contracts(self): # noqa
        contract_statuses = [
            CreditContractStatus.ISSUED,
            CreditContractStatus.REPAY,
            CreditContractStatus.RESTRUCTURED,
            CreditContractStatus.EXPIRED
        ]
        profile: Profile = self.request.user
        contract_query = CreditContract.objects.filter(
            borrower=profile.person,
            contract_status__in=contract_statuses
        )
        if not contract_query.exists():
            logger.info("У profile=%s, iin=%s не найдены контракты", profile, profile.person.iin)
            raise CreditContractNotFound

        return contract_query

    @swagger_auto_schema(
        responses={'200': serializers.CreditContractSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        contracts = self.get_contracts()
        serializer = serializers.CreditContractSerializer(contracts, many=True)

        return Response(serializer.data)


class ProfileCreditsView(APIView):
    """
    Получение данных по кредитам (список, конкретный кредит по pk, текущий кредит)
    """
    permission_classes = (IsProfileAuthenticated,)
    serializer_class = serializers.ProfileCreditApplicationSerializer
    http_method_names = ('get',)

    def get_queryset(self):
        """
        Получение всех кредитов, связанных с пользователем.
        """
        profile: Profile = self.request.user
        queryset = CreditApplication.objects.filter(borrower=profile.person).order_by('-created')

        if not queryset.exists():
            logger.info("У profile=%s, iin=%s не найдены кредиты", profile, profile.person.iin)
            raise CreditContractNotFound
        return queryset

    def get_object(self, pk):
        """
        Получение одного конкретного кредита по pk.
        """
        try:
            return CreditApplication.objects.get(pk=pk)
        except CreditApplication.DoesNotExist:
            logger.info(f"CreditApplication с id={pk} не найден")
            raise CreditContractNotFound

    def get_current_credit(self):
        """
        Получение последнего кредита пользователя.
        """
        queryset = self.get_queryset()
        return queryset.first() if queryset.exists() else None

    @swagger_auto_schema(
        responses={
            '200': serializers.ProfileCreditApplicationSerializer(many=True)
        }
    )
    def get(self, request, pk=None, *args, **kwargs):
        """
        Обработка GET-запроса:
        - Если указан `pk`, возвращается конкретный кредит.
        - Если `pk` не указан, возвращается список кредитов с полем `current_credit`.
        """
        if pk:
            credit = self.get_object(pk)
            serializer = self.serializer_class(credit)
            return Response(serializer.data)
        else:
            credits = self.get_queryset()
            current_credit = self.get_current_credit()

            data = {
                "credits": self.serializer_class(credits, many=True).data,
                "current_credit": self.serializer_class(current_credit).data if current_credit else None
            }
            return Response(data)
