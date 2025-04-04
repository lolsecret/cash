# Generated by Django 4.2.10 on 2025-03-03 12:37

import apps.accounts.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_bankcard_bankaccount'),
    ]

    operations = [
        migrations.AddField(
            model_name='profilepersonalrecord',
            name='average_monthly_income',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Средний ежемесячный доход'),
        ),
        migrations.AddField(
            model_name='profilepersonalrecord',
            name='bank_statement',
            field=models.FileField(blank=True, null=True, upload_to=apps.accounts.models.bank_statement_path, verbose_name='Банковская выписка'),
        ),
        migrations.AddField(
            model_name='profilepersonalrecord',
            name='income_calculated_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Дата расчета дохода'),
        ),
    ]
