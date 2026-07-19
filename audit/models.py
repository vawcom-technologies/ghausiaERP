from django.conf import settings
from django.db import models


class AuditModel(models.Model):
    """Abstract base model with audit and cancellation fields."""

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="%(class)s_created",
        null=True,
        blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="%(class)s_updated",
        null=True,
        blank=True,
    )
    is_cancelled = models.BooleanField(default=False)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="%(class)s_cancelled",
        null=True,
        blank=True,
    )
    cancellation_reason = models.TextField(blank=True)

    class Meta:
        abstract = True

    def cancel(self, user, reason: str) -> None:
        from django.utils import timezone

        self.is_cancelled = True
        self.cancelled_at = timezone.now()
        self.cancelled_by = user
        self.cancellation_reason = reason
        self.save(
            update_fields=[
                "is_cancelled",
                "cancelled_at",
                "cancelled_by",
                "cancellation_reason",
                "updated_at",
            ]
        )
