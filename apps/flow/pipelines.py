from celery import chain

from apps.credits.models import CreditApplication
from apps.notifications.tasks import notify_client_ws

from .tasks.fetchers import (
    fetch_gbdfl,
    fetch_gkb_income,
    fetch_pkb_behavioral,
    fetch_pkb_credit_report,
    fetch_service_1c_main_debt,
)
from .tasks.logic import (
    check_income,
    check_negative_statuses,
    check_person_in_blacklist,
    check_pkb_behavioral_score,
    check_main_debt_in_service_1c,
    final_decision,
)


def regular(credit: CreditApplication):
    iin = credit.borrower.iin
    pk = credit.pk
    c = chain(
        fetch_gbdfl.si(credit_pk=pk, iin=iin),
        check_person_in_blacklist.si(credit_pk=pk),
        fetch_service_1c_main_debt.si(credit_pk=pk, IIN=iin),
        fetch_pkb_behavioral.si(credit_pk=pk, iin=iin),
        check_pkb_behavioral_score.si(credit_pk=pk),
        final_decision.si(credit_pk=pk),
    )
    return c()


def full(credit: CreditApplication):
    iin = credit.borrower.iin
    pk = credit.pk
    c = chain(
        check_person_in_blacklist.si(credit_pk=pk),
        fetch_service_1c_main_debt.si(credit_pk=pk, IIN=iin),
        check_main_debt_in_service_1c.si(credit_pk=pk),
        fetch_pkb_behavioral.si(credit_pk=pk, iin=iin),
        check_pkb_behavioral_score.si(credit_pk=pk),
        fetch_gkb_income.si(credit_pk=pk, iin=iin),
        check_income.si(credit_pk=pk),
        fetch_pkb_credit_report.si(credit_pk=pk, iin=iin),
        check_negative_statuses.si(credit_pk=pk),
        final_decision.si(credit_pk=pk),
        notify_client_ws.si(lead_pk=credit.lead_id, payload={"approved": True}),
    )
    return c()
