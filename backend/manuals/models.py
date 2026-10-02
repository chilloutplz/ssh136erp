from django.conf import settings
from django.db import models


class ProductManual(models.Model):
    """사이드바 제품메뉴얼 링크."""

    product_name = models.CharField(max_length=100, unique=True)
    manual_url = models.URLField(max_length=500)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="product_manuals",
    )

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "제품메뉴얼"
        verbose_name_plural = "제품메뉴얼"

    def __str__(self):
        return self.product_name
