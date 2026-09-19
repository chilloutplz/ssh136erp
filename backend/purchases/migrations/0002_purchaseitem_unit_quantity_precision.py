from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("purchases", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="purchaseitem",
            name="unit",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.AlterField(
            model_name="purchaseitem",
            name="quantity",
            field=models.DecimalField(decimal_places=3, default=0, max_digits=14),
        ),
    ]
