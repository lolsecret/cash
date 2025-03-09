from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.http import Http404,HttpResponseForbidden
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import TimeStampedModel
from phonenumber_field.modelfields import PhoneNumberField
import logging
logger = logging.getLogger(__name__)

from apps.core.utils import generate_key

from apps.core.models import Branch
from apps.credits import CreditStatus
from . import Roles
from .managers import UserManager


class RoleGroupPermissions(models.Model):

    class Meta:
        verbose_name = _("Доступ по роли")
        verbose_name_plural = _("Доступы по ролям")

    group_permissions = models.ManyToManyField(
        Group,
        related_name="group_permissions",
        verbose_name=_("Доступы по ролям")
    )
    role = models.CharField(
        _("Роль"),
        max_length=30,
        choices=Roles.choices,
    )

    def get_role_permissions(self):
        groups_id = self.group_permissions.all().values_list('id', flat=True)
        role_permissions = Permission.objects.filter(group__id__in=groups_id)
        return role_permissions


class User(AbstractUser, TimeStampedModel):
    username = None
    groups = None
    user_permissions = None
    middle_name = models.CharField(_('middle name'), max_length=150, blank=True)
    email = models.EmailField("Email", unique=True)
    phone = PhoneNumberField(
        _('Phone'),
        null=True,
    )
    role = models.CharField(
        _("Роль"),
        max_length=30,
        choices=Roles.choices,
        null=True,
        blank=True,
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        null=True, blank=True,
        verbose_name="Филиал",
    )


    # email_confirm_token = models.CharField(max_length=40, null=True)
    # email_confirmation_sent_at = models.DateTimeField(null=True, default=timezone.now)
    # email_confirmed_at = models.DateTimeField(null=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    def get_user_role_groups(self):
        try:
            role_group = RoleGroupPermissions.objects.get(role=self.role)
        except RoleGroupPermissions.DoesNotExist:
            logger.error(f"Для роли {self.role} не были созданы доступы по группам")
            raise Http404()
        return role_group

    def get_user_role_permissions(self):
        role_group = self.get_user_role_groups()
        perms = role_group.get_role_permissions()
        return perms

    @property
    def get_user_groups(self):
        role_group = self.get_user_role_groups()
        return role_group.group_permissions.all()

    def set_random_password(self):
        password = get_random_string(length=12)
        self.set_password(password)
        return password

    @property
    def email_confirmed(self):
        return self.email_confirmed_at is not None

    def generate_email_confirm_token(self):
        self.email_confirm_token = generate_key()
        self.email_confirmation_sent_at = timezone.now()
        self.save(update_fields=["email_confirm_token", "email_confirmation_sent_at"])
        return self.email_confirm_token

    def email_confirm_verify(self, token: str):
        self.email_confirmed_at = timezone.now()
        self.save(update_fields=["email_confirmed_at"])

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self):
        if self.last_name and self.first_name:
            return " ".join([self.last_name, self.first_name])
        if self.email:
            return self.email
        return str(self.pk)

    @property
    def is_chairman(self) -> bool:
        return self.role == Roles.CREDIT_COMMITTEE_CHAIRMAN

    @property
    def is_role_admin(self) -> bool:
        return self.role == Roles.ROLE_ADMINISTRATOR and self.is_staff

    @property
    def is_accountant(self) -> bool:
        return self.role == Roles.ROLE_ACCOUNTANT

    @property
    def is_risk_manager(self) -> bool:
        return self.role == Roles.ROLE_RISK_MANAGER

    @property
    def is_director(self) -> bool:
        return self.role == Roles.ROLE_DIRECTOR

    @property
    def is_auditor(self) -> bool:
        return self.role == Roles.ROLE_AUDITOR

    @property
    def is_finance_controller(self):
        return self.role == Roles.ROLE_FINANCE_CONTROLLER

    @property
    def is_admin_supervisor(self) -> bool:
        return self.role == Roles.CREDIT_ADMIN_SUPERVISOR

    @property
    def is_credit_admin(self) -> bool:
        return self.role == Roles.CREDIT_ADMIN

    @property
    def is_admin(self) -> bool:
        return self.role in [Roles.CREDIT_ADMIN, Roles.ROLE_ADMINISTRATOR]

    @property
    def is_credit_manager(self) -> bool:
        return self.role == Roles.CREDIT_MANAGER

    @property
    def is_committee_member(self) -> bool:
        return self.role == Roles.CREDIT_COMMITTEE_MEMBER



    def count_leads(self):  # noqa
        from apps.credits.models import Lead
        return Lead.objects.exclude(rejected=True).count()

    def count_credit_applications(self):  # noqa
        from apps.credits.models import CreditApplication
        active_statuses = (CreditStatus.IN_WORK,
                           CreditStatus.CALLBACK,
                           CreditStatus.DECISION,
                           CreditStatus.IN_PROGRESS,
                           CreditStatus.FIN_ANALYSIS,
                           CreditStatus.FILLING,
                           CreditStatus.DECISION_CHAIRPERSON,
                           CreditStatus.ISSUANCE,)
        return CreditApplication.objects.filter(status__in=active_statuses).count()


class StatusPermission(TimeStampedModel):
    class Meta:
        verbose_name = "Доступ к кредитам по статусам"
        verbose_name_plural = "Доступы к кредитам по статусам"
        unique_together = ("group", "status", "permission")

    group = models.ForeignKey(
        Group,
        on_delete=models.PROTECT,
        related_name="status_permissions",
        verbose_name=_("Доступы по статусам")
    )
    status = models.CharField(_("Статус"), choices=CreditStatus.choices, max_length=20)
    permission = models.ForeignKey(
        "auth.Permission",  # noqa
        on_delete=models.PROTECT,
        related_name="status_permissions",
        verbose_name=_("Доступы по статусам")
    )


class ProxyGroup(Group):
    class Meta:
        proxy = True
        verbose_name = "Группа"
        verbose_name_plural = "Группы"