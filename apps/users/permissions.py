from copy import deepcopy

from rest_framework.permissions import DjangoModelPermissions
from rest_framework.permissions import BasePermission


class UserPermission(DjangoModelPermissions):
    def __init__(self):
        self.perms_map = deepcopy(self.perms_map)
        self.perms_map['GET'] = ['%(app_label)s.view_%(model_name)s']


class BaseRolePermission(BasePermission):
    # Base class with standard permissions

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_active


# Администратор
class AdminPermission(BaseRolePermission):
    def has_permission(self, request, view):
        return (
                super().has_permission(request, view)
                and request.user.is_role_admin
                and request.user.is_staff
        )


# Бухгалтер
class AccountantPermission(BaseRolePermission):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.is_accountant


# Риск Менеджер
class RiskManagerPermission(BaseRolePermission):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.is_risk_manager


# Директор
class DirectorPermission(BaseRolePermission):

    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.is_director


# Аудитор
class AuditorPermission(BaseRolePermission):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.is_auditor


# Финансовый контролер
class FinanceControllerPermission(BaseRolePermission):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.is_finance_controller


# Супервайзер кредитных администраторов
class AdminSupervisorPermission(BaseRolePermission):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.is_admin_supervisor


# Кредитный администратор
class CreditAdminPermission(BaseRolePermission):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.is_credit_admin


# Кредитный менеджер
class CreditManagerPermission(BaseRolePermission):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.is_credit_manager


#  Председатель КК
class CreditCommitteeChairmanPermission(BaseRolePermission):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.is_chairman


# Член КК
class CreditCommitteeMemberPermission(BaseRolePermission):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.is_committee_member


