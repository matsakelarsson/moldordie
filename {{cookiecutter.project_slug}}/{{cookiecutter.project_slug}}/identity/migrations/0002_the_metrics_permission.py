from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("identity", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="serviceregistration",
            options={
                "ordering": ["name"],
                "permissions": [("read_metrics", "Can read the metrics")],
                "verbose_name": "service registration",
                "verbose_name_plural": "service registrations",
            },
        ),
    ]
