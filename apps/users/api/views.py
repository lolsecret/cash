from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.models import User

from . import serializers


class ProfileView(APIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.UserSerializer

    def get_queryset(self):
        return self.request.user

    def get(self, request, *args, **kwargs):
        instance = self.get_queryset()
        serializer = self.serializer_class(instance)
        return Response(serializer.data)


class ManagerList(ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.UserSerializer
    queryset = User.objects.managers().exclude(is_active=False)
