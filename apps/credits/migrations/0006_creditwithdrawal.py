# Generated by Django 4.2.10 on 2025-03-15 22:44

from django.db import migrations, models
import django.db.models.deletion
import django_extensions.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('credits', '0005_alter_creditapplicationpayment_options_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='CreditWithdrawal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='Сумма вывода')),
                ('status', models.CharField(choices=[('PENDING', 'Ожидает обработки'), ('PROCESSING', 'В процессе'), ('COMPLETED', 'Завершен'), ('FAILED', 'Ошибка'), ('CANCELED', 'Отменен')], db_index=True, default='PENDING', max_length=50, verbose_name='Статус')),
                ('order_id', models.CharField(blank=True, db_index=True, max_length=100, null=True, unique=True, verbose_name='Идентификатор заказа')),
                ('tokenize_transaction_id', models.CharField(blank=True, max_length=100, null=True, verbose_name='ID транзакции токенизации')),
                ('tokenize_form_url', models.URLField(blank=True, max_length=500, null=True, verbose_name='URL для токенизации карты')),
                ('withdrawal_response', models.JSONField(blank=True, null=True, verbose_name='Ответ платежной системы')),
                ('error_message', models.TextField(blank=True, null=True, verbose_name='Сообщение об ошибке')),
                ('completed_at', models.DateTimeField(blank=True, null=True, verbose_name='Дата завершения')),
                ('contract', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='withdrawals', to='credits.creditcontract', verbose_name='Кредитный контракт')),
            ],
            options={
                'verbose_name': 'Вывод средств',
                'verbose_name_plural': 'Выводы средств',
                'ordering': ['-created'],
            },
        ),
    ]
