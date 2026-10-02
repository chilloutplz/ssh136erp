from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def seed_product_manuals(apps, schema_editor):
    ProductManual = apps.get_model("manuals", "ProductManual")
    seeds = [
        {
            "product_name": "전어 미나리 가이드",
            "manual_url": "https://seasonal-jeoneo-minari-guide.challoo.chatgpt.site/#order",
            "sort_order": 10,
        },
        {
            "product_name": "새우 가이드",
            "manual_url": "https://seasonal-shrimp-guide.challoo.chatgpt.site/",
            "sort_order": 20,
        },
        {
            "product_name": "치킨난반 가이드",
            "manual_url": "https://chicken-nanban-guide.challoo.chatgpt.site/",
            "sort_order": 30,
        },
    ]
    for row in seeds:
        ProductManual.objects.get_or_create(
            product_name=row["product_name"],
            defaults={
                "manual_url": row["manual_url"],
                "sort_order": row["sort_order"],
            },
        )


def unseed_product_manuals(apps, schema_editor):
    ProductManual = apps.get_model("manuals", "ProductManual")
    ProductManual.objects.filter(
        product_name__in=[
            "전어 미나리 가이드",
            "새우 가이드",
            "치킨난반 가이드",
        ]
    ).delete()


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductManual",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("product_name", models.CharField(max_length=100, unique=True)),
                ("manual_url", models.URLField(max_length=500)),
                ("sort_order", models.IntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="product_manuals",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "제품메뉴얼",
                "verbose_name_plural": "제품메뉴얼",
                "ordering": ["sort_order", "id"],
            },
        ),
        migrations.RunPython(seed_product_manuals, unseed_product_manuals),
    ]
