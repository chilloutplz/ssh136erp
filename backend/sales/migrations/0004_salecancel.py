# Generated manually for SaleCancel

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0003_alter_sale_payment_status"),
    ]

    operations = [
        migrations.CreateModel(
            name="SaleCancel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source", models.CharField(max_length=20)),
                ("store_code", models.CharField(max_length=50)),
                ("channel_order_no", models.CharField(blank=True, default="", max_length=100)),
                ("cancelled_at", models.DateTimeField()),
                ("cancel_reason", models.TextField(blank=True, default="")),
                ("cancel_amount", models.BigIntegerField(default=0)),
                ("business_date", models.DateField(blank=True, null=True)),
                (
                    "process_note",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text="원주문 미매칭·유니크 충돌 등 처리 메시지 (프론트 알림용)",
                    ),
                ),
                ("is_read", models.BooleanField(default=False)),
                ("raw_data", models.JSONField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "sale",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="cancels",
                        to="sales.sale",
                    ),
                ),
            ],
            options={
                "ordering": ["-cancelled_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="salecancel",
            index=models.Index(fields=["business_date"], name="sales_salec_busines_idx"),
        ),
        migrations.AddIndex(
            model_name="salecancel",
            index=models.Index(fields=["is_read", "-created_at"], name="sales_salec_is_read_idx"),
        ),
        migrations.AddIndex(
            model_name="salecancel",
            index=models.Index(
                fields=["source", "store_code", "channel_order_no"],
                name="sales_salec_source_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="salecancel",
            constraint=models.UniqueConstraint(
                fields=("source", "store_code", "channel_order_no", "cancelled_at"),
                name="uniq_salecancel_source_store_orderno_cancelledat",
            ),
        ),
    ]
