from rest_framework import serializers


# noinspection PyAbstractClass
class PKBBiometricSerializer(serializers.Serializer):
    borrower_photo = serializers.ImageField()
    document_photo = serializers.ImageField(read_only=True)
    similarity = serializers.FloatField(read_only=True)
    attempts = serializers.IntegerField(read_only=True)
