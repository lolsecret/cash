from django.db.models.aggregates import Count
from django.db.models.query_utils import Q

from apps.credits.models import Product
from apps.credits import CreditStatus


def get_product_list(request):
    active_statuses = (
        CreditStatus.IN_WORK,
        CreditStatus.CALLBACK,
        CreditStatus.DECISION,
        CreditStatus.IN_PROGRESS,
        CreditStatus.FIN_ANALYSIS,
        CreditStatus.FILLING,
        CreditStatus.DECISION_CHAIRPERSON,
        CreditStatus.ISSUANCE,
    )
    products_qs = Product.objects.annotate(
        credits_count=Count('credits', filter=Q(credits__status__in=active_statuses))
    ).values('pk', 'name', 'credits_count')

    return {
        'product_list': products_qs
    }
