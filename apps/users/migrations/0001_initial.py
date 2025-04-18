# Generated by Django 4.2.10 on 2024-11-26 11:02

import django.contrib.auth.models
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import django_extensions.db.fields
import phonenumber_field.modelfields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('core', '0001_initial'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProxyGroup',
            fields=[
            ],
            options={
                'verbose_name': 'Группа',
                'verbose_name_plural': 'Группы',
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('auth.group',),
            managers=[
                ('objects', django.contrib.auth.models.GroupManager()),
            ],
        ),
        migrations.CreateModel(
            name='RoleGroupPermissions',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('CREDIT_ADMIN_SUPERVISOR', 'Супервайзер кредитных администраторов'), ('CREDIT_ADMIN', 'Кредитный администратор'), ('CREDIT_MANAGER', 'Кредитный менеджер'), ('CREDIT_COMMITTEE_CHAIRMAN', 'Председатель КК'), ('CREDIT_COMMITTEE_MEMBER', 'Член КК'), ('ADMIN', 'Администратор'), ('ACCOUNTANT', 'Бухгалтер'), ('RISK_MANAGER', 'Риск менеджер'), ('DIRECTOR', 'Директор'), ('AUDITOR', 'Аудитор'), ('FINANCE_CONTROLLER', 'Финансовый контролер')], max_length=30, verbose_name='Роль')),
                ('group_permissions', models.ManyToManyField(related_name='group_permissions', to='auth.group', verbose_name='Доступы по ролям')),
            ],
            options={
                'verbose_name': 'Доступ по роли',
                'verbose_name_plural': 'Доступы по ролям',
            },
        ),
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('first_name', models.CharField(blank=True, max_length=150, verbose_name='first name')),
                ('last_name', models.CharField(blank=True, max_length=150, verbose_name='last name')),
                ('is_staff', models.BooleanField(default=False, help_text='Designates whether the user can log into this admin site.', verbose_name='staff status')),
                ('is_active', models.BooleanField(default=True, help_text='Designates whether this user should be treated as active. Unselect this instead of deleting accounts.', verbose_name='active')),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now, verbose_name='date joined')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('middle_name', models.CharField(blank=True, max_length=150, verbose_name='middle name')),
                ('email', models.EmailField(max_length=254, unique=True, verbose_name='Email')),
                ('phone', phonenumber_field.modelfields.PhoneNumberField(max_length=128, null=True, region=None, verbose_name='Phone')),
                ('role', models.CharField(blank=True, choices=[('CREDIT_ADMIN_SUPERVISOR', 'Супервайзер кредитных администраторов'), ('CREDIT_ADMIN', 'Кредитный администратор'), ('CREDIT_MANAGER', 'Кредитный менеджер'), ('CREDIT_COMMITTEE_CHAIRMAN', 'Председатель КК'), ('CREDIT_COMMITTEE_MEMBER', 'Член КК'), ('ADMIN', 'Администратор'), ('ACCOUNTANT', 'Бухгалтер'), ('RISK_MANAGER', 'Риск менеджер'), ('DIRECTOR', 'Директор'), ('AUDITOR', 'Аудитор'), ('FINANCE_CONTROLLER', 'Финансовый контролер')], max_length=30, null=True, verbose_name='Роль')),
                ('branch', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='core.branch', verbose_name='Филиал')),
            ],
            options={
                'verbose_name': 'Пользователь',
                'verbose_name_plural': 'Пользователи',
            },
        ),
        migrations.CreateModel(
            name='StatusPermission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('status', models.CharField(choices=[('NEW', 'Новая'), ('IN_PROGRESS', 'В процессе'), ('IN_WORK', 'В работе'), ('IN_WORK_CREDIT_ADMIN', 'В работе (кред.админ)'), ('TO_SIGNING', 'На подписании'), ('GUARANTOR_SIGNING', 'На подписании гаранта'), ('FIN_ANALYSIS', 'Фин Анализ'), ('DECISION', 'На рассмотрении'), ('DECISION_CHAIRPERSON', 'Ожидает решение (председатель)'), ('FILLING', 'На доработке'), ('VISIT', 'Выезд'), ('CALLBACK', 'Перезвонить'), ('APPROVED', 'Одобрен'), ('REJECTED', 'Отказ'), ('CANCEL', 'Отмена'), ('ISSUANCE', 'Выдача'), ('ISSUED', 'Выдан')], max_length=20, verbose_name='Статус')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='status_permissions', to='auth.group', verbose_name='Доступы по статусам')),
                ('permission', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='status_permissions', to='auth.permission', verbose_name='Доступы по статусам')),
            ],
            options={
                'verbose_name': 'Доступ к кредитам по статусам',
                'verbose_name_plural': 'Доступы к кредитам по статусам',
                'unique_together': {('group', 'status', 'permission')},
            },
        ),
    ]
