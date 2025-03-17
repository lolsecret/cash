import re

from django.db.models import Q
from django.utils.translation import gettext as _
from django_filters import rest_framework as filters

from apps.credits.models import Lead, CreditApplication, RejectionReason


# noinspection DuplicatedCode
class LeadListFilter(filters.FilterSet):
    created_start = filters.DateFilter(field_name='created', lookup_expr='date__gte')
    created_end = filters.DateFilter(field_name='created', lookup_expr='date__lte')
    q = filters.CharFilter(method='q_custom_filter', label=_("Search"))

    class Meta:
        model = Lead
        fields = ['product', 'rejected']

    # noinspection PyMethodMayBeStatic
    def q_custom_filter(self, queryset, name, value):
        query = Q()
        if re.match(r"\d", value):
            query.add(Q(pk=value), Q.OR)

        query.add(Q(mobile_phone__contains=value), Q.OR)
        query.add(Q(borrower__iin__startswith=value), Q.OR)
        query.add(Q(borrower_data__last_name__icontains=value), Q.OR)
        return queryset.filter(query)


# noinspection DuplicatedCode
# noinspection PyMethodMayBeStatic
class CreditListFilter(filters.FilterSet):
    created_gte = filters.DateFilter(field_name='created', lookup_expr='date__gte')
    created_lte = filters.DateFilter(field_name='created', lookup_expr='date__lte')
    search = filters.CharFilter(method='q_custom_filter', label=_("Search"))

    class Meta:
        model = CreditApplication
        fields = ['status', 'product', 'id']

    def search_custom_filter(self, queryset, name, value):
        query = Q()
        if re.match(r"\d", value):
            query.add(Q(pk=value), Q.OR)

        query.add(Q(lead__mobile_phone__contains=value), Q.OR)
        query.add(Q(borrower__iin__startswith=value), Q.OR)
        query.add(Q(borrower_data__last_name__icontains=value), Q.OR)
        query.add(Q(business_info__name__icontains=value), Q.OR)
        return queryset.filter(query)


class RejectionReasonFilter(filters.FilterSet):
    search = filters.CharFilter(method='search_custom_filter', label=_("Search"))

    class Meta:
        model = RejectionReason
        fields = ['status', 'active', 'order']

    def search_custom_filter(self, queryset, name, value):
        query = Q()
        if re.match(r"\d", value):
            query.add(Q(pk=value), Q.OR)
            query.add(Q(order=value), Q.OR)

        query.add(Q(status__icontains=value), Q.OR)
        return queryset.filter(query)
