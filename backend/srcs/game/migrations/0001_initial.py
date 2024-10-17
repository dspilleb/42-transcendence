# Generated by Django 4.2 on 2024-10-16 11:54

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Match',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user1_score', models.IntegerField(default=0)),
                ('user2_score', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
            ],
        ),
    ]