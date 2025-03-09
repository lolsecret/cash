import logging
from typing import Dict, Any

from apps.core.models import Branch, City
from apps.core.utils import chained_pipeline
from apps.credits import RepaymentMethod
from apps.credits.models import CreditParams, Lead
from apps.people.models import Person, PersonalData, Address

logger = logging.getLogger(__name__)


def create_borrower(validated_data: Dict[str, Any]) -> PersonalData:
    logger.info("#static.pipelines call create_borrower iin=%s", validated_data["iin"], extra=validated_data)
    person = Person.objects.get_create_from_iin(validated_data["iin"])
    return PersonalData.objects.create(
        person=person,
        reg_address=Address.objects.create(),
        real_address=Address.objects.create(),
        mobile_phone=validated_data["mobile_phone"],
    )


def create_lead(validated_data: Dict[str, Any], borrower_data: PersonalData) -> Lead:
    logger.info("#static.pipelines call create_lead iin=%s", validated_data["iin"], extra=validated_data)
    credit_params = CreditParams.objects.create(
        principal=validated_data["desired_amount"],
        period=validated_data["desired_period"],
        interest_rate=validated_data["product"].interest_rate,
        repayment_method=validated_data.get("repayment_method", RepaymentMethod.ANNUITY),
    )
    return Lead.objects.create(
        borrower=borrower_data.person,
        borrower_data=borrower_data,
        first_name=borrower_data.first_name,
        last_name=borrower_data.last_name,
        middle_name=borrower_data.middle_name,
        product=validated_data["product"],
        credit_params=credit_params,
        mobile_phone=validated_data["mobile_phone"],
        # channel=validated_data["channel"],    # временно убрал, оставим для CPA
        branch=Branch.objects.first(),
        cpa_transaction_id=validated_data.get('cpa_transaction_id'),
        utm_source=validated_data.get('utm_source'),
        utm_params=validated_data.get('utm'),
        city=validated_data.get('city', City.objects.first())
    )


lead_from_api_pipeline = chained_pipeline(
    create_borrower,
    create_lead
)
