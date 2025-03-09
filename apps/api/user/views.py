from rest_framework.response import Response
from rest_framework.views import APIView


class ActiveRequestView(APIView):
    """Активные заявки. Пока не ясно что мы должны тут показывать."""

    def get(self, request, pk: int):
        return Response([])
