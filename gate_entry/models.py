from django.db import models

from audit.models import AuditModel


class GateEntry(AuditModel):
    """One gate-in stock demand / purchase row (G1, G2, …)."""

    gate_number = models.CharField(
        "Gate No.",
        max_length=20,
        unique=True,
        help_text="Auto numbers like G1, G2, G3…",
    )
    entry_date = models.DateField("Date")
    purchaser = models.CharField("Purchaser", max_length=200)
    shop_name = models.CharField("Shop Name", max_length=200)
    chemical = models.CharField("Chemical", max_length=255, blank=True, default="")
    electrical = models.CharField("Electrical", max_length=255, blank=True, default="")
    mechanical = models.CharField("Mechanical", max_length=255, blank=True, default="")
    general = models.CharField("General", max_length=255, blank=True, default="")
    demanded_by = models.CharField("Demanded By", max_length=200)
    entry_image = models.ImageField(
        "Photo",
        upload_to="gate_entry/%Y/%m/",
        blank=True,
        null=True,
        help_text="Optional photo — compressed automatically to save space.",
    )

    class Meta:
        ordering = ["gate_number"]
        verbose_name = "Gate Entry"
        verbose_name_plural = "Gate Entries"

    def __str__(self) -> str:
        return self.gate_number
