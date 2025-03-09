from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Optional

from dateutil.relativedelta import relativedelta
from django.core.cache import cache
from django.db.models import Count, Sum, Avg
from django.utils import timezone

from apps.core.models import CreditIssuancePlan
from apps.credits import CreditStatus
from apps.credits.models import Channel, Lead, CreditApplication
from apps.credits.reports.utils import get_start_of_month, get_end_of_month, get_start_of_year, get_end_of_year

RU_MONTHS = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь",
             "Декабрь"]


class DashboardReport:
    def __init__(self, *, start_date: date, end_date: date, sales_channel: Optional[Channel]) -> None:
        self.sales_channel = sales_channel

        start_date = start_date or datetime.now().date()
        end_date = end_date or datetime.now().date()

        self.start_date = timezone.make_aware(datetime.combine(start_date, time.min))
        self.end_date = timezone.make_aware(datetime.combine(end_date, time.max))

        self.start_of_month = get_start_of_month(start_date)
        self.end_of_month = get_end_of_month(start_date)

        self.start_of_year = get_start_of_year(start_date)
        self.end_of_year = get_end_of_year(start_date)

    def prepare(self):
        pass

    @property
    def lead_qs(self):
        return Lead.objects.filter(
            created__gte=self.start_date,
            created__lte=self.end_date,
        )

    @property
    def credit_qs(self):
        return CreditApplication.objects.filter(
            created__gte=self.start_date,
            created__lte=self.end_date,
        )

    @property
    def credit_month_qs(self):
        return CreditApplication.objects.filter(
            created__gte=self.start_of_month,
            created__lte=self.end_of_month,
        )

    @property
    def credit_year_qs(self):
        return CreditApplication.objects.filter(
            created__gte=self.start_of_year,
            created__lte=self.end_of_year,
        )

    @property
    def cache_key(self):
        return f"dashboard-report-start-{self.start_date}-end-{self.end_date}-channel-{self.sales_channel}"

    def cache_get(self):
        return cache.get(self.cache_key)

    def cache_set(self, data: dict):
        cache.set(self.cache_key, data, 60)

    def issued_data(self):
        issued_data = self.credit_month_qs.filter(
            status=CreditStatus.ISSUED,
        ).aggregate(
            credits_issued_count=Count('id'),
            credits_issued_sum=Sum('approved_params__principal'),
        )
        issued_data['credits_issued_sum'] = issued_data['credits_issued_sum'] or 0
        return issued_data

    def in_work_data(self):
        in_work_statuses = (CreditStatus.IN_WORK,
                            CreditStatus.CALLBACK,
                            CreditStatus.DECISION,
                            CreditStatus.FIN_ANALYSIS,
                            CreditStatus.FILLING,)
        in_work_data = self.credit_month_qs.filter(
            status__in=in_work_statuses,
        ).aggregate(
            credits_in_work_count=Count('id'),
            credits_in_work_sum=Sum('requested_params__principal'),
        )
        in_work_data['credits_in_work_sum'] = in_work_data['credits_in_work_sum'] or 0

        return in_work_data

    def managers_plan(self):
        manager_credits = list(self.credit_year_qs.filter(
            status=CreditStatus.ISSUED,
            manager__isnull=False,
        ).values_list(
            'created__year',
            'created__month',
            'manager__id',
            'manager__first_name',
            'manager__last_name',
        ).annotate(
            issued_credits=Sum('approved_params__principal'),
        ).order_by(
            'created__year',
            'created__month',
        ))

        issuance_plans = {plan.year: {plan.month: plan.issuance_plan} for plan in CreditIssuancePlan.objects.all()}

        # Если не указан ежемесячный план, найдем максимальную сумму за год.
        # Это будет верхним порогом, чтобы график правильно отображался.
        max_principal_sum = int(max([row[-1] for row in manager_credits])) if manager_credits else 0

        manager_report = {}
        for year, month, manager_id, manager_first_name, manager_last_name, principal_sum in manager_credits:
            principal_sum = int(principal_sum)

            issuance_plan = issuance_plans.get(year, {}).get(month, 0)

            if manager_id not in manager_report:
                manager_report[manager_id] = {
                    'name': f"{manager_last_name} {manager_first_name}",
                    'monthly_data': {}
                }

            percent: float = principal_sum / issuance_plan if issuance_plan else principal_sum / max_principal_sum
            manager_report[manager_id]['monthly_data'][month] = round(percent * 100)

        for manager in manager_report.values():  # type: dict
            monthly_data = manager.pop('monthly_data')
            manager['data'] = []

            for month in range(1, 13):
                manager['data'].append(monthly_data.get(month, 0))

        return list(manager_report.values())

    def issuance_dynamics(self):
        issuance_months_totals = self.credit_year_qs.filter(
            status=CreditStatus.ISSUED,
        ).values_list(
            'created__month',
        ).annotate(
            credits_issued_count=Count('id'),
            credits_issued_principal_sum=Sum('approved_params__principal'),
        ).order_by(
            'created__month',
        ).values_list(
            'created__month',
            'credits_issued_count',
            'credits_issued_principal_sum',
        )

        credits_issued_count = []
        credits_issued_principal_sum = []

        report = {}
        for month, issued_count, issued_principal_sum in issuance_months_totals:  # type: dict
            report[month] = {
                'credits_issued_count': issued_count,
                'credits_issued_principal_sum': issued_principal_sum,
            }

        for month in range(1, 13):
            issued_count = report.get(month, {}).get('credits_issued_count', 0)
            issued_principal_sum = report.get(month, {}).get('credits_issued_principal_sum', 0)
            credits_issued_count.append(issued_count)
            credits_issued_principal_sum.append(issued_principal_sum)

        return [
            {'type': 'column',
             'name': 'Суммы выданных займов, млн.тг',
             'data': credits_issued_principal_sum},
            {'type': 'line',
             'name': 'Кол-во выданных займов, шт.',
             'data': credits_issued_count},
        ]

    def statistics(self):
        issuance_months_totals = self.credit_year_qs.filter(
            status=CreditStatus.ISSUED,
        ).values_list(
            'created__month',
        ).annotate(
            credits_issued_count=Count('id'),
            credits_issued_principal_sum=Sum('approved_params__principal'),
            credits_issued_principal_average=Avg('approved_params__principal'),
            credits_issued_interest_rate_average=Avg('approved_params__interest_rate'),
            credits_issued_period_average=Avg('approved_params__period'),
        ).order_by(
            'created__month',
        ).values(
            'created__month',
            'credits_issued_count',
            'credits_issued_principal_sum',
            'credits_issued_interest_rate_average',
            'credits_issued_period_average',
        )

        res = defaultdict()
        for month_data in issuance_months_totals:
            month = month_data.pop('created__month')
            res[month] = month_data

        stat = {
            'credits_issued_count': {
                'type': 'line',
                'name': 'Кол-во активных клиентов, шт.',
                'data': [],
            },
            'credits_issued_principal_sum': {
                'type': 'column',
                'name': 'Ср.сумма, млн.тг',
                'data': [],
            },
            # 'credits_issued_principal_average': [],
            'credits_issued_interest_rate_average': {
                'type': 'line',
                'name': 'Ср.ставка, %',
                'data': [],
            },
            'credits_issued_period_average': {
                'type': 'line',
                'name': 'Ср.срок кредита, мес.',
                'data': [],
            },
        }
        for month in range(1, 13):
            stat['credits_issued_count']['data'].append(res.get(month, {}).get('credits_issued_count', 0))
            stat['credits_issued_principal_sum']['data'].append(
                res.get(month, {}).get('credits_issued_principal_sum', 0)
            )
            stat['credits_issued_period_average']['data'].append(
                round(res.get(month, {}).get('credits_issued_period_average', 0), 2)
            )
            stat['credits_issued_interest_rate_average']['data'].append(
                res.get(month, {}).get('credits_issued_interest_rate_average', 0)
            )

        return list(stat.values())

    def rejected_credits(self):
        rejected_credits = self.credit_qs.filter(
            created__gte=self.start_date,
            created__lte=self.end_date,
        ).filter(
            reject_reason__isnull=False,
            status=CreditStatus.REJECTED,
        ).values_list(
            'reject_reason__status',
        ).annotate(
            reject_count=Count('id'),
        ).order_by(
            'reject_count'
        )

        return {reject_reason: reject_count for reject_reason, reject_count in rejected_credits}

    def rejected_leads(self):
        rejected_leads = self.lead_qs.filter(
            rejected=True,
            reject_reason__isnull=False,
        ).values_list(
            'reject_reason',
        ).annotate(
            reject_count=Count('id'),
        ).order_by(
            'reject_count',
        )

        return {reject_reason: reject_count for reject_reason, reject_count in rejected_leads}

    def utm_sources(self):
        qs = self.lead_qs.objects.filter(
            utm_source__isnull=False
        ).values_list(
            'utm_source'
        ).annotate(
            total=Count('utm_source'),
        ).order_by('total')
        result = {}

        for utm_name, utm_count in qs:
            if utm_name is None:
                utm_name = 'Сайт МФО'

            result[utm_name] = utm_count

        return result

    def sales_funnel(self):
        not_active_status = [CreditStatus.REJECTED, CreditStatus.IN_PROGRESS, CreditStatus.NEW]

        lead_qs = self.lead_qs
        credit_qs = self.credit_qs

        if self.sales_channel:
            lead_qs = lead_qs.filter(channel=self.sales_channel)
            credit_qs = credit_qs.filter(lead__channel=self.sales_channel)

        leads_count = lead_qs.count()

        pipelined_leads_count = lead_qs.filter(
            rejected=False,
            reject_reason__isnull=True,
        ).count()

        km_applications_count = credit_qs.filter(
            reject_reason__isnull=True,
        ).exclude(
            status__in=not_active_status,
        ).count()

        issued_applications_count = credit_qs.filter(
            status=CreditStatus.ISSUED,
        ).count()

        return {
            "Все каналы": {
                "leads": leads_count,
                "pipelined_leads": pipelined_leads_count,
                "km_applications": km_applications_count,
                "issued_applications": issued_applications_count,
                "conversion": km_applications_count / leads_count if leads_count else 0,
                "ar": issued_applications_count / km_applications_count if km_applications_count else 0,
            }
        }

    def get(self) -> dict:
        cache_data = self.cache_get()
        if cache_data is not None:
            return cache_data

        data = {
            "ru_months": RU_MONTHS,

            # 1
            **self.issued_data(),

            # 2
            **self.in_work_data(),

            # 4
            "manager_plan": self.managers_plan(),

            # 5-6
            "issuance_dynamics": self.issuance_dynamics(),

            #
            "statistics": self.statistics(),

            # 7
            "rejected_by_km": self.rejected_credits(),
            "rejected_by_system": self.rejected_leads(),

            # 8
            "sales_funnel": self.sales_funnel(),
        }

        self.cache_set(data)
        return data
