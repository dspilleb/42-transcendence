# Generated by Django 5.1.2 on 2024-11-09 14:56

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0006_alter_customuser_avatar'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='last_connection',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]
