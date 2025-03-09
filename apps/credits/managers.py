import logging
from typing import TYPE_CHECKING
from datetime import date, timedelta

from django.contrib.auth.models import Permission, User
from django.db.models import QuerySet, Q
from django.db.models.manager import BaseManager
from django.utils import timezone

from apps.credits import CreditStatus, DocumentCategory, Decision
if TYPE_CHECKING:
    from .models import Lead, CreditApplication

logger = logging.getLogger(__name__)


class LeadQueryset(QuerySet):
    def stuck(self):
        one_day = timezone.now() - timedelta(hours=24)
        return self.filter(
            is_done=False,
            created__gt=one_day,
        )

    def pending(self):
        return self.filter(rejecte=False, verified=False)

    def verified(self):
        return self.filter(verified=True)


class CreditApplicationQueryset(QuerySet):
    def active(self):
        return self.exclude(
            status__in=[
                CreditStatus.REJECTED,
                CreditStatus.APPROVED,
                CreditStatus.ISSUED,
            ]
        )

    def new(self):
        return self.filter(status=CreditStatus.NEW)

    def rejected(self):
        return self.filter(status=CreditStatus.REJECTED)

    def approved(self):
        return self.filter(status=CreditStatus.APPROVED)

    def signed(self):
        return self.filter(otp_signature__isnull=False)

    def for_borrower(self, borrower):
        return self.select_related("borrower").filter(
            borrower=borrower
        )

    def with_requested_params(self):
        return self.filter(requested_params__isnull=False)

    def without_requested_params(self):
        return self.filter(requested_params__isnull=True)

    def today(self):
        return self.filter(created_at__date=date.today())

    def credits_by_permissions(self, user):
        model_permission = Permission.objects.filter(
            content_type__app_label=self.model._meta.app_label,  # noqa
            codename="view_creditapplication"
        ).first()

        is_credit_manager = user.is_credit_manager
        statuses_permit = user.get_user_groups.filter(status_permissions__permission=model_permission) \
            .values_list("status_permissions__status")
        filters = Q(status__in=statuses_permit)

        if is_credit_manager:
            filters &= Q(manager=user)

        return self.filter(filters)


class CreditApplicationManager(BaseManager.from_queryset(CreditApplicationQueryset)):
    def create_from_lead(self, lead: 'Lead') -> 'CreditApplication':
        from apps.references.models import IndividualProprietorList
        from .models import BusinessInfo

        # credit_params = model_to_dict(lead.credit_params, exclude=['id'])
        # recommended_params = CreditParams.objects.create(**credit_params)
        # approved_params = CreditParams.objects.create(**credit_params)
        credit, created = self.get_or_create(  # type: CreditApplication, bool # noqa
            lead=lead,
            defaults={
                'borrower': lead.borrower,
                'borrower_data': lead.borrower_data,
                'requested_params': lead.credit_params,
                'product': lead.product,
            }
        )
        credit.init_credit_params()

        lead.done()

        return credit


class DocumentTypeQuerySet(QuerySet):
    def borrower_docs(self):
        return self.filter(group=DocumentCategory.BORROWER_DOCS)

    def credit_docs(self):
        return self.filter(group=DocumentCategory.CREDIT_DOCS, active=True)

    def guarantor_docs(self):
        return self.filter(group=DocumentCategory.GUARANTOR_DOCS)

    def financial_analysis_docs(self):
        return self.filter(group=DocumentCategory.FINANCIAL_ANALYSIS_DOCS)

    def other_docs(self):
        return self.filter(group=DocumentCategory.OTHER_DOCS)


class CreditDecisionVoteQueryset(QuerySet):
    def chairman(self):
        return self.filter(
            manager__role__is_committee_member=True, manager__role__is_chairman=True
        ).first()

    def negative(self):
        return self.filter(status=Decision.AGAINST)

    def positive(self):
        return self.filter(status=Decision.FOR)
