# Generated: supplier contact fields + SupplierAlias + Purchase.supplier_draft
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("purchases", "0002_purchaseitem_unit_quantity_precision"),
    ]

    operations = [
        migrations.AddField(
            model_name="supplier",
            name="representative",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
        migrations.AddField(
            model_name="supplier",
            name="phone",
            field=models.CharField(blank=True, default="", max_length=30),
        ),
        migrations.AddField(
            model_name="supplier",
            name="fax",
            field=models.CharField(blank=True, default="", max_length=30),
        ),
        migrations.AddField(
            model_name="supplier",
            name="email",
            field=models.EmailField(blank=True, default="", max_length=254),
        ),
        migrations.AddField(
            model_name="supplier",
            name="address",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="purchase",
            name="supplier_draft",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="SupplierAlias",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("raw_name", models.CharField(max_length=200)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("supplier", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name="aliases", to="purchases.supplier")),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("supplier", "raw_name"), name="uniq_supplier_alias_rawname"
                    )
                ],
            },
        ),
    ]
