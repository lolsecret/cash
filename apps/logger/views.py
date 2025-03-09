import re
from io import BytesIO
from typing import Tuple, Optional
from zipfile import ZipFile, ZIP_DEFLATED

import orjson
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpResponse
from django.views.generic import ListView, DetailView
from lxml import etree

from apps.logger.models import Log


class LogListView(ListView):
    model = Log
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_superuser:
            raise PermissionDenied("Permission denied")

        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset()
        query = self.request.GET.get('q')

        if query:
            qs = qs.filter(
                Q(uid=query) | Q(iin=query)
            )

        return qs


class LogDetailView(DetailView):
    model = Log

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_superuser:
            raise PermissionDenied("Permission denied")

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['object_list'] = self.get_queryset().filter(
            uid=context['object'].uid,
        ).order_by('pk')
        context['object_count'] = len(context['object_list'])
        return context


class LogDownloadView(LogDetailView):
    # noinspection PyMethodMayBeStatic
    def get_file_type(self, instance: Log, index: Optional[int] = None) -> Tuple[str, str]:
        """Делаем читаемый формат запрос/ответ
        Определяем тип сообщения json/xml/txt.
        """
        req_type = '_request'
        if instance.response_status is not None:
            req_type = '_response'

        method = re.sub("[^a-zA-Z]+", "_", instance.method)
        if method.startswith('_'):
            method = method[1:]

        message = instance.content
        file_type = '.txt'
        try:
            temp = orjson.loads(message.replace('@', ''))
            message = orjson.dumps(temp, option=orjson.OPT_INDENT_2)
            file_type = '.json'

        except Exception as exc:  # noqa
            try:
                message = re.sub(r'>[\n\t\r ]+<', '><', message)
                temp = etree.fromstring(message)
                message = etree.tostring(temp, pretty_print=True, encoding=str)
                file_type = '.xml'

            except Exception:  # noqa
                pass

        filename = f"{method}{req_type}{file_type}"
        if index is not None:
            filename = f"{index}_{filename}"

        return message, filename

    def get(self, request, *args, **kwargs):
        instance: Log = self.get_object()

        if request.GET.get('logs') == 'all':
            return self.download_logs_by_uid_archive(
                queryset=self.get_queryset().filter(uid=instance.uid).order_by('pk'),
            )

        message, filename = self.get_file_type(instance)
        response = HttpResponse(instance.content, content_type='text/plain')
        response['Content-Disposition'] = 'attachment; filename=%s' % filename
        return response

    def download_logs_by_uid_archive(self, *, queryset):
        """Скачать логи архивом по queryset-у"""
        log_objects = []
        for index, log in enumerate(queryset, start=1):
            log_objects.append(self.get_file_type(log, index=index))

        in_memory = BytesIO()
        with ZipFile(in_memory, 'w', compression=ZIP_DEFLATED) as zip_file:
            for message, filename in log_objects:
                zip_file.writestr(filename, message)

        response = HttpResponse(content_type="application/zip")
        response["Content-Disposition"] = "attachment; filename=logs.zip"

        in_memory.seek(0)
        response.write(in_memory.read())
        in_memory.close()

        return response
