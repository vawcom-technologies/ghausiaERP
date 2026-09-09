from django.conf import settings
from django.db import models

from accounts.modules import MODULE_CHOICES, MODULE_LABELS


class WorkAssignment(models.Model):
    """Which factory area a data-entry user is allowed to work in."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="work_assignments",
    )
    module = models.CharField(max_length=50, choices=MODULE_CHOICES)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assignments_made",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "module")
        ordering = ["user__username", "module"]

    def __str__(self) -> str:
        return f"{self.user} → {MODULE_LABELS.get(self.module, self.module)}"


class PermanentDeleteRequest(models.Model):
    """Supervisor asks an administrator to wipe a recycled record."""

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Waiting for admin"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    )

    model_key = models.CharField(max_length=50)
    object_pk = models.PositiveIntegerField()
    module = models.CharField(max_length=80)
    label = models.CharField(max_length=255)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="permanent_delete_requests",
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="permanent_delete_reviews",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-requested_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["model_key", "object_pk"],
                condition=models.Q(status="pending"),
                name="unique_pending_permanent_delete",
            )
        ]

    def __str__(self) -> str:
        return f"{self.label} ({self.get_status_display()})"
