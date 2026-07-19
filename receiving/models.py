from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from audit.models import AuditModel
from master_data.models import ClothType, Employee, Vendor


class ClothReceipt(AuditModel):
    receipt_number = models.CharField(max_length=50, unique=True)
    receipt_date = models.DateField()
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name="receipts")
    vendor_challan_number = models.CharField(max_length=100)
    cloth_type = models.ForeignKey(ClothType, on_delete=models.PROTECT, related_name="receipts")
    number_of_rolls = models.PositiveIntegerField(default=0)
    vendor_metres = models.DecimalField(max_digits=12, decimal_places=3)
    factory_measured_metres = models.DecimalField(max_digits=12, decimal_places=3)
    vendor_weight = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    factory_measured_weight = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    rejected_metres = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    accepted_metres = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    metre_difference = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    weight_difference = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    production_lot_number = models.CharField(
        "Lot Number / Palli Number",
        max_length=50,
        unique=True,
        help_text="Main lot / palli number used across all production stages.",
    )
    received_by = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="receipts_received",
        null=True,
        blank=True,
    )
    checked_by = models.ForeignKey(
        Employee, on_delete=models.PROTECT, related_name="receipts_checked", null=True, blank=True
    )
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ["-receipt_date", "-id"]

    def __str__(self) -> str:
        return self.production_lot_number or self.receipt_number

    def calculate_fields(self) -> None:
        self.metre_difference = self.vendor_metres - self.factory_measured_metres
        self.weight_difference = self.vendor_weight - self.factory_measured_weight
        self.accepted_metres = self.factory_measured_metres - self.rejected_metres

    def clean(self) -> None:
        self.calculate_fields()
        # Keep internal receipt_number aligned with lot / palli number.
        if self.production_lot_number and not self.receipt_number:
            self.receipt_number = self.production_lot_number
        if self.number_of_rolls < 0:
            raise ValidationError({"number_of_rolls": "Number of rolls cannot be negative."})
        if self.rejected_metres > self.factory_measured_metres:
            raise ValidationError(
                {"rejected_metres": "Rejected metres cannot exceed factory measured metres."}
            )
        if self.accepted_metres < 0:
            raise ValidationError({"accepted_metres": "Accepted metres cannot be negative."})

    def save(self, *args, **kwargs):
        if self.production_lot_number:
            self.receipt_number = self.production_lot_number
        self.calculate_fields()
        super().save(*args, **kwargs)
