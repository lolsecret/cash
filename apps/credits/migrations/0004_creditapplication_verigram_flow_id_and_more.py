# Generated by Django 4.2.10 on 2025-03-09 14:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('credits', '0003_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='creditapplication',
            name='verigram_flow_id',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='ID Flow Verigram'),
        ),
        migrations.AddField(
            model_name='creditapplication',
            name='verigram_flow_url',
            field=models.URLField(blank=True, max_length=1000, null=True, verbose_name='URL Flow Verigram'),
        ),
    ]
