from datetime import timedelta
from typing import Tuple, Optional

from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
# from django.contrib.auth.modals import UserManager as BaseUserManager
from django.db.models import Q, Model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.users import Roles


class UserManager(BaseUserManager):
    def create_user(self, email=None, password=None, **extra_fields):
        if not email:
            raise ValueError(_('The given email must be set'))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password, **extra_fields):
        """
        Create and save a SuperUser with the given email and password.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        return self.create_user(email, password, **extra_fields)

    def get_by_email_confirm_token(self, token) -> Optional[Model]:
        return self.filter(email_confirm_token=token).first()

    def email_confirm_token(self, token) -> Tuple[bool, Optional[Model], str]:
        time_expire = timedelta(minutes=settings.EXPIRATION_TIME_CONFIRM_URL)
        user = self.filter(email_confirm_token=token).first()

        if not user or (user.email_confirmation_sent_at + time_expire) < timezone.now():
            return False, None, "Ссылка неверная или истек срок действия ссылки на потверждение email"

        if user.email_confirmed:
            return False, None, "Уже email потвержден"

        user.email_confirmed_at = timezone.now()
        user.save(update_fields=['email_confirmed_at'])
        return True, user, ""

    def managers(self):
        return self.filter(role__in=[Roles.CREDIT_MANAGER])
