# Generated by Django 4.1.4 on 2024-04-01 20:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ping_pong', '0011_alter_user_otp'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='otp',
            field=models.CharField(blank=True, max_length=6, null=True),
        ),
    ]
