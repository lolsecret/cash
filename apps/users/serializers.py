from rest_framework import serializers
from django.apps import apps
from django.contrib.auth.models import Permission

from .models import (
    User,
    # Role,
)


# class RoleViewSerializer(serializers.ModelSerializer):
#     const_name = serializers.CharField(source="name")
#     name = serializers.CharField(source="get_name_display")
#
#     class Meta:
#         model = Role
#         fields = ["id", "name", "const_name"]


class PermissionSerializer(serializers.Serializer):
    def to_representation(self, instance) -> dict:
        models = [
            apps.get_model("credits", "CreditApplication"),
            apps.get_model("products", "Product"),
            User,
        ]

        models = [{"name": model._meta.model_name, "label": model._meta.app_label} for model in models]

        # add custom perms to list
        models.append({"name": "tab", "label": "tab"})

        permission_list = {model['name']: self.get_model_perms(model) for model in models}

        return permission_list

    def get_model_perms(self, model):
        perms = Permission.objects.filter(content_type__model=model["name"]).values_list("codename", flat=True)

        return {perm: self.instance.has_perm(f"{model['label']}.{perm}") for perm in perms}


class ManagerSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()
    branch = serializers.SerializerMethodField()

    def get_branch(self, instance) -> str:
        return instance.branch.name if instance.branch else ""

    class Meta:
        model = User
        fields = ["full_name", "branch"]


class UserInfoSerializer(serializers.ModelSerializer):
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["permissions"]

    def get_permissions(self, instance):
        serializer = PermissionSerializer(instance)
        return serializer.data


class UserViewSerializer(serializers.ModelSerializer):
    """
    List, Retrieve serializer for User model
    """

    role = serializers.SerializerMethodField()

    def get_role(self, instance) -> str:
        return instance.role.name if instance.role else ""

    class Meta:
        model = User
        fields = [
            "id",
            "first_name", "middle_name", "last_name",
            "role", "email", "is_active", "branch",
        ]


class UserCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Create, Update serializer for User model
    """
    class Meta:
        model = User
        fields = [
            "id",
            "first_name", "middle_name", "last_name",
            "role", "email", "password", "is_active",
            "branch",
        ]

        extra_kwargs = {field: {"required": True} for field in fields if not field == "id"}
        extra_kwargs["password"] = {"write_only": True}

    def update(self, instance, validated_data):
        if validated_data.get("password"):
            instance.set_password(validated_data.pop("password"))

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance

    def create(self, validated_data):
        request = self.context["request"]
        validated_data["partner"] = request.user.partner
        return User.objects.create(**validated_data)
