from django.db.models import TextChoices


class Roles(TextChoices):
    CREDIT_ADMIN_SUPERVISOR = "CREDIT_ADMIN_SUPERVISOR", "Супервайзер кредитных администраторов"
    CREDIT_ADMIN = "CREDIT_ADMIN", "Кредитный администратор"
    CREDIT_MANAGER = "CREDIT_MANAGER", "Кредитный менеджер"
    CREDIT_COMMITTEE_CHAIRMAN = "CREDIT_COMMITTEE_CHAIRMAN", "Председатель КК"
    CREDIT_COMMITTEE_MEMBER = "CREDIT_COMMITTEE_MEMBER", "Член КК"
    ROLE_ADMINISTRATOR = "ADMIN", "Администратор"
    ROLE_ACCOUNTANT = "ACCOUNTANT", "Бухгалтер"
    ROLE_RISK_MANAGER = "RISK_MANAGER", "Риск менеджер"
    ROLE_DIRECTOR = "DIRECTOR", "Директор"
    ROLE_AUDITOR = "AUDITOR", "Аудитор"
    ROLE_FINANCE_CONTROLLER = "FINANCE_CONTROLLER", "Финансовый контролер"
