from apps.flow import RejectReason


class ServiceUnavailable(Exception):
    """Сервис не доступен"""


class ServiceErrorException(Exception):
    """Сервис вернул ошибку"""

    def __init__(self, *args: object, response=None) -> None:
        super().__init__(*args)
        self.response = response


class RejectRequestException(Exception):
    """Отклонить запрос"""

    def __init__(self, message, *args: object) -> None:
        if isinstance(message, RejectReason):
            message = message.name
        super().__init__(message, *args)
