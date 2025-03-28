# Generated by Django 4.2.10 on 2024-11-26 11:02

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('core', '0001_initial'),
        ('people', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('credits', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='creditdecisionvote',
            name='manager',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='manager_decisions', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='creditdecision',
            name='credit',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='decisions', to='credits.creditapplication'),
        ),
        migrations.AddField(
            model_name='creditcontract',
            name='borrower',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='contracts', to='people.person', verbose_name='Заёмщик'),
        ),
        migrations.AddField(
            model_name='creditcontract',
            name='credit',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='contract', to='credits.creditapplication', verbose_name='Заявка'),
        ),
        migrations.AddField(
            model_name='creditcontract',
            name='params',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='credits.creditparams', verbose_name='Параметры кредита'),
        ),
        migrations.AddField(
            model_name='creditcontract',
            name='product',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='contracts', to='credits.product', verbose_name='Продукт'),
        ),
        migrations.AddField(
            model_name='creditcontract',
            name='signed_user_content_type',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype'),
        ),
        migrations.AddField(
            model_name='creditapplicationpayment',
            name='contract',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='contract_payments', to='credits.creditcontract', verbose_name='Кредитный контракт'),
        ),
        migrations.AddField(
            model_name='creditapplicationpayment',
            name='person',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='contract_payments', to='people.person', verbose_name='Физическое лицо'),
        ),
        migrations.AddField(
            model_name='creditapplication',
            name='approved_params',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='credits_approved', to='credits.creditparams', verbose_name='Подтвержденные параметры'),
        ),
        migrations.AddField(
            model_name='creditapplication',
            name='borrower',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='credits', to='people.person', verbose_name='Заёмщик'),
        ),
        migrations.AddField(
            model_name='creditapplication',
            name='borrower_data',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='credits', to='people.personaldata', verbose_name='Анкета заемщика'),
        ),
        migrations.AddField(
            model_name='creditapplication',
            name='guarantors_records',
            field=models.ManyToManyField(related_name='guarantor_application', through='credits.Guarantor', to='people.personaldata'),
        ),
        migrations.AddField(
            model_name='creditapplication',
            name='lead',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='credit', to='credits.lead', to_field='uuid', verbose_name='Лид'),
        ),
        migrations.AddField(
            model_name='creditapplication',
            name='manager',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Менеджер'),
        ),
        migrations.AddField(
            model_name='creditapplication',
            name='partner',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installment_loans', to='core.partner', verbose_name='Партнер'),
        ),
        migrations.AddField(
            model_name='creditapplication',
            name='product',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='credits', to='credits.product', verbose_name='Программа'),
        ),
        migrations.AddField(
            model_name='creditapplication',
            name='recommended_params',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='credits_recommended', to='credits.creditparams', verbose_name='Рекомендуемые параметры'),
        ),
        migrations.AddField(
            model_name='creditapplication',
            name='reject_reason',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='credits.rejectionreason', verbose_name='Причина отказа'),
        ),
        migrations.AddField(
            model_name='creditapplication',
            name='requested_params',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='credits_requested', to='credits.creditparams', verbose_name='Запрашиваемые параметры'),
        ),
        migrations.AddField(
            model_name='comment',
            name='author',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='Автор'),
        ),
        migrations.AddField(
            model_name='comment',
            name='credit',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comments', to='credits.creditapplication'),
        ),
        migrations.AddField(
            model_name='businessinfo',
            name='credit',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='business_info', to='credits.creditapplication'),
        ),
        migrations.AddField(
            model_name='applicationfacematchphoto',
            name='credit',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='biometry_photos', to='credits.creditapplication'),
        ),
        migrations.AlterUniqueTogether(
            name='repaymentplan',
            unique_together={('product', 'repayment_method')},
        ),
        migrations.AlterUniqueTogether(
            name='documenttype',
            unique_together={('code', 'group')},
        ),
        migrations.AlterUniqueTogether(
            name='creditdecisionvote',
            unique_together={('manager', 'decision')},
        ),
    ]
