from django_filters import rest_framework as filters
from django.db.models import Q
import re
from django.utils.translation import gettext_lazy as _

from apps.users.models import User


class UserListFilter(filters.FilterSet):
    created_gte = filters.DateFilter(field_name='date_joined', lookup_expr='date__gte')
    created_lte = filters.DateFilter(field_name='date_joined', lookup_expr='date__lte')
    search = filters.CharFilter(method='search_custom_filter', label=_("Search"))

    class Meta:
        model = User
        fields = ['role', 'is_active', 'branch', 'id']

    def search_custom_filter(self, queryset, name, value):
        query = Q()
        if re.match(r"\d", value):
            query.add(Q(pk=value), Q.OR)

        query.add(Q(email__icontains=value), Q.OR)
        query.add(Q(phone__contains=value), Q.OR)
        query.add(Q(last_name__icontains=value), Q.OR)
        query.add(Q(first_name__icontains=value), Q.OR)
        query.add(Q(middle_name__icontains=value), Q.OR)
        return queryset.filter(query)
