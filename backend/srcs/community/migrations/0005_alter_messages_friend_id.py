# Generated by Django 5.1.2 on 2024-11-13 11:55

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('community', '0004_messages'),
    ]

    operations = [
        migrations.AlterField(
            model_name='messages',
            name='friend_id',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='friend_chat_id', to='community.friend'),
        ),
    ]
