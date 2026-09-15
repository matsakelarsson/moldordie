from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="ServiceRegistration",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100, unique=True, verbose_name="name")),
                ("enabled", models.BooleanField(default=True, verbose_name="enabled")),
                (
                    "subject",
                    models.CharField(
                        {%- if cookiecutter.identity_provider == 'entra' %}
                        help_text="The object id of the service's service principal in the tenant.",
                        {%- else %}
                        help_text="The unique id of the service account (the sub claim of its tokens).",
                        {%- endif %}
                        max_length=255,
                        unique=True,
                        verbose_name="subject",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="created at")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="updated at")),
                (
                    "permissions",
                    models.ManyToManyField(
                        blank=True,
                        related_name="service_registrations",
                        to="auth.permission",
                        verbose_name="permissions",
                    ),
                ),
            ],
            options={
                "verbose_name": "service registration",
                "verbose_name_plural": "service registrations",
                "ordering": ["name"],
            },
        ),
    ]
