import json
import logging
from logging import Handler, LogRecord

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)


class DBHandler(Handler):

    def __init__(self, model) -> None:
        super().__init__()
        self.model = model

    def emit(self, record: LogRecord) -> None:
        try:
            log_model = import_string(self.model)
            log_entry = log_model(level=record.levelname, content=self.format(record))

            try:
                data = json.loads(record.msg)
                for key, value in list(data.items()):
                    if hasattr(log_entry, key):
                        try:
                            setattr(log_entry, key, value)

                        except:
                            pass

                    elif key == 'message':
                        log_entry.content = value

            except Exception as exc:
                logger.error("log entry error %s", exc)

            log_entry.save(using='logger')

        except Exception as exc:
            logger.error('Could not log: %s', exc)


class DBLogger:
    """
    Класс для логирования внешних запросов.
    """

    db_logger = logging.getLogger('db_logger')

    @classmethod
    def info(cls, message, **kwargs):
        try:
            kwargs['message'] = message.decode() if isinstance(message, bytes) else message
            cls.db_logger.info(json.dumps(kwargs, cls=DjangoJSONEncoder))

        except Exception as exc:
            logger.error("DBLogger.info write error %s", exc)

    @classmethod
    def warning(cls, message, **kwargs):
        kwargs['message'] = message.decode() if isinstance(message, bytes) else message
        cls.db_logger.warning(json.dumps(kwargs, cls=DjangoJSONEncoder))

    @classmethod
    def error(cls, message, **kwargs):
        try:
            kwargs['message'] = message.decode() if isinstance(message, bytes) else message
            cls.db_logger.error(json.dumps(kwargs, cls=DjangoJSONEncoder))

        except Exception as exc:
            logger.error("DBLogger.error write error %s", exc)
