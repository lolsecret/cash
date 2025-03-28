# Generated by Django 4.2.10 on 2024-11-26 11:02

from django.db import migrations, models
import django.db.models.deletion
import django_extensions.db.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('credits', '0001_initial'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExternalService',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Название')),
                ('service_class', models.CharField(max_length=255, null=True, verbose_name='Класс сервиса')),
                ('address', models.CharField(blank=True, max_length=255, null=True, verbose_name='Адрес')),
                ('username', models.CharField(blank=True, max_length=255, null=True, verbose_name='Имя пользователя')),
                ('password', models.CharField(blank=True, max_length=255, null=True, verbose_name='Пароль')),
                ('token', models.CharField(blank=True, max_length=255, null=True, verbose_name='Api token')),
                ('timeout', models.PositiveIntegerField(blank=True, null=True, verbose_name='Таймаут (сек.)')),
                ('cache_lifetime', models.PositiveIntegerField(null=True, verbose_name='Время жизни кэша (дней)')),
                ('params', models.JSONField(null=True, verbose_name='Параметры')),
                ('is_active', models.BooleanField(default=False, verbose_name='Активен')),
            ],
            options={
                'verbose_name': 'Внешний сервис',
                'verbose_name_plural': 'Внешние сервисы',
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='Pipeline',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Наименование')),
                ('is_active', models.BooleanField(default=False, verbose_name='Активен')),
                ('background', models.BooleanField(default=False, verbose_name='Фоновый режим')),
            ],
            options={
                'verbose_name': 'Конвейер',
                'verbose_name_plural': 'Настройки: Список конвейеров',
            },
        ),
        migrations.CreateModel(
            name='ServiceHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('object_id', models.PositiveIntegerField(null=True)),
                ('reference_id', models.CharField(blank=True, max_length=255, null=True)),
                ('data', models.JSONField(blank=True, null=True, verbose_name='Данные')),
                ('status', models.CharField(choices=[('NO_REQUEST', 'Не было запроса'), ('WAS_REQUEST', 'Был запрос'), ('CHECKED', 'Проверено'), ('REQUEST_ERROR', 'Ошибка запроса'), ('SERVICE_UNAVAILABLE', 'Сервис не доступен'), ('CACHED_REQUEST', 'Заполнен из кэша')], default='NO_REQUEST', max_length=20, verbose_name='Статус')),
                ('runtime', models.DecimalField(decimal_places=3, default=0.0, max_digits=6, verbose_name='Выполнено за(сек)')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, null=True, verbose_name='Дата запроса')),
                ('request_id', models.CharField(blank=True, max_length=32, null=True, verbose_name='Request-id')),
                ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype')),
                ('pipeline', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='services_history', to='flow.pipeline', verbose_name='Конвейер')),
                ('service', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='flow.externalservice', verbose_name='Сервис')),
            ],
            options={
                'verbose_name': 'История запросов',
                'verbose_name_plural': 'Сервисы: История запросов',
                'ordering': ('-pk',),
            },
        ),
        migrations.CreateModel(
            name='ServiceResponse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('url', models.CharField(blank=True, max_length=255, null=True, verbose_name='Ссылка')),
                ('method', models.CharField(blank=True, max_length=100, null=True, verbose_name='Метод')),
                ('request', models.TextField(blank=True, null=True, verbose_name='Параметры запроса')),
                ('response', models.TextField(blank=True, null=True, verbose_name='Ответ от сервиса')),
                ('history', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='service_response', to='flow.servicehistory', verbose_name='Лог')),
            ],
            options={
                'verbose_name': 'Лог сервиса',
                'verbose_name_plural': 'Логи сервисов',
            },
        ),
        migrations.CreateModel(
            name='ServiceReason',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=255, unique=True, verbose_name='Ключ')),
                ('message', models.CharField(max_length=255, verbose_name='Отказное сообщение')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активен')),
                ('service', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='flow.externalservice', verbose_name='Сервис')),
            ],
            options={
                'verbose_name': 'Негативный статус',
                'verbose_name_plural': 'Настройки: Негативные статусы',
                'ordering': ('service', 'key'),
            },
        ),
        migrations.CreateModel(
            name='Job',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('priority', models.PositiveSmallIntegerField(default=0, verbose_name='Порядок выполнения')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активен')),
                ('raise_exception', models.BooleanField(default=False, verbose_name='Вызвать исключение')),
                ('pipeline', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='jobs', to='flow.pipeline')),
                ('service', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='flow.externalservice', verbose_name='Сервис')),
            ],
            options={
                'verbose_name': 'Задача',
                'verbose_name_plural': 'Задачи',
            },
        ),
        migrations.CreateModel(
            name='BiometricConfiguration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('service', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='flow.externalservice', verbose_name='Сервис')),
            ],
            options={
                'verbose_name': 'Biometric Configuration',
                'verbose_name_plural': 'Biometric Configuration',
            },
        ),
        migrations.CreateModel(
            name='StatusTrigger',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Название')),
                ('status', models.CharField(choices=[('NEW', 'Новая'), ('IN_PROGRESS', 'В процессе'), ('IN_WORK', 'В работе'), ('IN_WORK_CREDIT_ADMIN', 'В работе (кред.админ)'), ('TO_SIGNING', 'На подписании'), ('GUARANTOR_SIGNING', 'На подписании гаранта'), ('FIN_ANALYSIS', 'Фин Анализ'), ('DECISION', 'На рассмотрении'), ('DECISION_CHAIRPERSON', 'Ожидает решение (председатель)'), ('FILLING', 'На доработке'), ('VISIT', 'Выезд'), ('CALLBACK', 'Перезвонить'), ('APPROVED', 'Одобрен'), ('REJECTED', 'Отказ'), ('CANCEL', 'Отмена'), ('ISSUANCE', 'Выдача'), ('ISSUED', 'Выдан')], max_length=20, verbose_name='Статус')),
                ('priority', models.PositiveIntegerField(default=0, verbose_name='Приоритет')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активен')),
                ('pipeline', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='flow.pipeline', verbose_name='Конвейер')),
                ('product', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='credits.product', verbose_name='Программа')),
            ],
            options={
                'verbose_name': 'Триггер смены статуса',
                'verbose_name_plural': 'Настройки: Триггеры',
                'unique_together': {('status', 'priority')},
            },
        ),
        migrations.AddIndex(
            model_name='servicehistory',
            index=models.Index(fields=['created_at'], name='flow_servic_created_9ea1cf_idx'),
        ),
    ]
