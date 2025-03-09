from rest_framework.exceptions import APIException


class LeadRejected(APIException):
    status_code = 400
    default_detail = "Заявка не проходит по требованиям"


class RejectedByScoring(APIException):
    status_code = 400
    default_detail = "Заявка отклонена по результатам скоринга"
