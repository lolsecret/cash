import datetime

from apps.credits.models import CreditApplication


def get_nearest_maturity(credit: CreditApplication) -> dict:
    current_date = datetime.date.today()
    payments = [payment.__dict__ for payment in credit.contract.params.payment_schedule.payments]
    nearest_payment = min(payments, key=lambda x: abs(x['maturity_date'] - current_date))
    return nearest_payment
