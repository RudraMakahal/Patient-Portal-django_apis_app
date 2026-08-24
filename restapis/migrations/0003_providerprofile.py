import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("restapis", "0002_providerrequest"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ProviderProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("first_name", models.CharField(max_length=80)),
                ("last_name", models.CharField(max_length=80)),
                ("email", models.EmailField(max_length=254)),
                ("specialty", models.CharField(max_length=120)),
                ("license_number", models.CharField(max_length=120)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="provider_profile", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["first_name", "last_name"],
            },
        ),
    ]
