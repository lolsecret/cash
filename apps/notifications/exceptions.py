from rest_framework.exceptions import APIException


class InvalidOTP(APIException):
    status_code = 400
    default_detail = "Неверный OTP-код"


class RepeatAgain(APIException):
    status_code = 400
    default_detail = "Неверный код. Попробуйте еще раз"


class GetNewOTP(APIException):
    status_code = 400
    default_detail = "Вы исчерпали количество попыток ввода кода. Получите код повторно"

class ExpiredOTP(APIException):
    status_code = 400
    default_detail = "Время действия кода истекло. Получите код повторно"
