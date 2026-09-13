from django.db import models


class WebhookEventLog(models.Model):
    """
    tosspos 등 외부 웹훅 수신 이력.
    x-toss-webhook-id 를 멱등 키로 사용해 중복 처리를 막고,
    처리 실패 시 재처리/디버깅에 사용한다.
    """

    class Source(models.TextChoices):
        TOSSPOS = "TOSSPOS", "토스포스"

    source = models.CharField(max_length=20, choices=Source.choices)
    webhook_id = models.CharField(max_length=100, db_index=True)  # x-toss-webhook-id
    event_id = models.CharField(max_length=100, null=True, blank=True)  # x-toss-event-id
    event_type = models.CharField(max_length=100, blank=True, default="")
    payload = models.JSONField()

    is_processed = models.BooleanField(default=False)
    error_message = models.TextField(null=True, blank=True)

    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source", "webhook_id"], name="uniq_webhook_source_id"
            )
        ]

    def __str__(self):
        return f"[{self.source}] {self.event_type} ({self.webhook_id})"
