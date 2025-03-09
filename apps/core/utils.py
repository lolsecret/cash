import binascii
import logging
import os
import uuid

import jwt

from django.conf import settings

from random import randint
from datetime import date

from functools import reduce
from typing import Callable, TypeVar

from django.utils import timezone
from rest_framework.exceptions import ValidationError, ErrorDetail

from apps.core.models import NotificationText


logger = logging.getLogger(__name__)


def random_number():
    return randint(int(1e11), int(1e12 - 1))


def generate_key():
    return binascii.hexlify(os.urandom(20)).decode()


def generate_uid():
    return uuid.uuid4().hex


def format_datetime(d) -> str:
    return timezone.localtime(d).strftime("%Y-%m-%dT%H:%M:%S")


def format_date(d: date) -> str:
    return d.strftime("%Y-%m-%d")


# Aliases:
_FirstType = TypeVar("_FirstType")
_SecondType = TypeVar("_SecondType")
_ThirdType = TypeVar("_ThirdType")
_ArgType = TypeVar("_ArgType")
_PipeType = TypeVar("_PipeType")
_LastPipeResultType = TypeVar("_LastPipeResultType")


def chain(
        ff: Callable[[_FirstType], _SecondType],
        sf: Callable[[_FirstType, _SecondType], _ThirdType]
) -> Callable[[_FirstType], _ThirdType]:
    return lambda arg: sf(arg, ff(arg))


def chained_flow(
        arg: _ArgType,
        *pipe_functions: _PipeType
) -> _LastPipeResultType:
    return reduce(chain, pipe_functions)(arg)


def chained_pipeline(*pipe_functions: _PipeType) -> Callable[[_ArgType], _LastPipeResultType]:
    return lambda arg: chained_flow(arg, *pipe_functions)


def decode_jwt_token(request):
    token = request.META.get('HTTP_AUTHORIZATION', " ").split(' ')[1]
    return jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])


def raise_notification_error(code: str):
    try:
        notification_text = NotificationText.objects.get(code=code)
    except NotificationText.DoesNotExist:
        msg = f"Для кода {code} не были созданы текста для уведомлений"
        detail = ErrorDetail(msg, code="notification_text_does_not_exist")
        logger.error(msg)

        raise ValidationError({"detail": detail})

    raise ValidationError(
        detail={notification_text.error_field: notification_text.text},
        code=code
    )