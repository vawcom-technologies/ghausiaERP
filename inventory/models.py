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


class ChemicalIssueSlip(AuditModel):
    """Chemicals issue slip row — all values stored as alphanumeric text."""

    issue_date = models.CharField("Date", max_length=50)
    issue_slip_number = models.CharField("Issue Slip Number", max_length=100)
    name = models.CharField("Name", max_length=200)
    department = models.CharField("Department", max_length=200)
    weight_kgs = models.CharField("Weight (kgs)", max_length=100, blank=True, default="")
    lot_number = models.CharField("LOT NO.", max_length=100, blank=True, default="")
    jet_number = models.CharField("Jet No.", max_length=100, blank=True, default="")
    jigar_number = models.CharField("Jigar No.", max_length=100, blank=True, default="")
    total_issued = models.CharField("Total Issued", max_length=100, blank=True, default="")

    class Meta:
        ordering = ["-id"]
        verbose_name = "Chemical Issue Slip"
        verbose_name_plural = "Chemical Issue Slips"

    def __str__(self) -> str:
        return self.issue_slip_number or f"Issue #{self.pk}"


class ChemicalStock(AuditModel):
    """Chemicals stock register row."""

    stock_date = models.CharField("Date", max_length=50)
    name = models.CharField("Name", max_length=200)
    closing_stock = models.CharField("Closing Stock", max_length=100, blank=True, default="")
    new_stock = models.CharField("New Stock", max_length=100, blank=True, default="")
    total_stock = models.CharField("Total Stock", max_length=100, blank=True, default="")
    issued_stock = models.CharField("Issued Stock", max_length=100, blank=True, default="")
    remaining_stock = models.CharField("Remaining Stock", max_length=100, blank=True, default="")

    class Meta:
        ordering = ["-id"]
        verbose_name = "Chemical Stock"
        verbose_name_plural = "Chemical Stock"

    def __str__(self) -> str:
        return f"{self.name} ({self.stock_date})"
