from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from audit.models import AuditModel
from master_data.models import Material


class MaterialTransaction(AuditModel):
    TRANSACTION_TYPE_CHOICES = [
        ("Purchase", "Purchase"),
        ("Dyeing Usage", "Dyeing Usage"),
        ("Mixture Usage", "Mixture Usage"),
        ("Maintenance Usage", "Maintenance Usage"),
        ("Adjustment In", "Adjustment In"),
        ("Adjustment Out", "Adjustment Out"),
        ("Return", "Return"),
        ("Reversal", "Reversal"),
    ]

    transaction_number = models.CharField(max_length=50, unique=True)
    transaction_date = models.DateField()
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="transactions")
    transaction_type = models.CharField(max_length=50, choices=TRANSACTION_TYPE_CHOICES)
    quantity_in = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    quantity_out = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    unit = models.CharField(max_length=20)
    dyeing_batch = models.ForeignKey(
        "production.DyeingBatch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="material_transactions",
    )
    mixture = models.ForeignKey(
        "production.Mixture",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="material_transactions",
    )
    maintenance_job = models.ForeignKey(
        "maintenance.MaintenanceJob",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="material_transactions",
    )
    dyeing_material_usage = models.ForeignKey(
        "production.DyeingMaterialUsage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="material_transactions",
    )
    maintenance_material_usage = models.ForeignKey(
        "maintenance.MaintenanceMaterialUsage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="material_transactions",
    )
    related_reference = models.CharField(max_length=200, blank=True)
    remarks = models.TextField(blank=True)
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="material_transactions_entered",
        null=True,
        blank=True,
    )
    reversed_transaction = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reversals",
    )

    class Meta:
        ordering = ["-transaction_date", "-id"]
        indexes = [
            models.Index(fields=["material", "transaction_date"]),
            models.Index(fields=["transaction_type"]),
        ]

    def __str__(self) -> str:
        return self.transaction_number

    def clean(self) -> None:
        if self.quantity_in > 0 and self.quantity_out > 0:
            raise ValidationError("A transaction cannot have both quantity in and quantity out.")
        if self.quantity_in <= 0 and self.quantity_out <= 0:
            raise ValidationError("At least one quantity must be greater than zero.")
        if self.quantity_in < 0 or self.quantity_out < 0:
            raise ValidationError("Quantity cannot be negative.")
