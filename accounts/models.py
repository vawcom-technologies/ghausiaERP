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
