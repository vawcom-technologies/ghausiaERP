from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from audit.models import AuditModel
from master_data.models import ClothType, Employee, Vendor


def parse_text_decimal(value, default: Decimal | None = None) -> Decimal:
    """Parse free-text weight/qty to Decimal when numeric; otherwise default/zero."""
    if default is None:
        default = Decimal("0")
    if isinstance(value, Decimal):
        return value
    text = str(value or "").strip().replace(",", "")
    if not text or text in {"/", "-", "—"}:
        return default
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return default


class ClothReceipt(AuditModel):
    receipt_number = models.CharField(max_length=50, unique=True)
    receipt_date = models.DateField()
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name="receipts")
    vendor_challan_number = models.CharField(max_length=100, blank=True, default="")
    cloth_type = models.ForeignKey(ClothType, on_delete=models.PROTECT, related_name="receipts")
    pv_blend_qty = models.CharField(
        "PV blend",
        max_length=50,
        blank=True,
        default="",
        help_text="Amount or code — digits and / allowed (e.g. 80 or 80/40). Use / for blank.",
    )
    read_pick_qty = models.CharField(
        "Read Pick",
        max_length=50,
        blank=True,
        default="",
        help_text="Amount or code — digits and / allowed (e.g. 80 or 80/40). Use / for blank.",
    )
    number_of_rolls = models.PositiveIntegerField(
        "Party Thaan (پارٹی تھان نمبر)",
        default=0,
    )
    factory_number_of_rolls = models.PositiveIntegerField(
        "Factory Thaan (فیکٹری تھان نمبر)",
        default=0,
    )
    vendor_metres = models.DecimalField(
        "Vendor M (پارٹی غزانہ)",
        max_digits=12,
        decimal_places=3,
    )
    factory_measured_metres = models.DecimalField(
        "Factory M (فیکٹری غزانہ)",
        max_digits=12,
        decimal_places=3,
    )
    vendor_weight = models.CharField(
        "Vendor wt",
        max_length=50,
        blank=True,
        default="",
    )
    factory_measured_weight = models.CharField(
        "Factory wt",
        max_length=50,
        blank=True,
        default="",
    )
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
    receipt_image = models.ImageField(
        "Photo",
        upload_to="receiving/%Y/%m/",
        blank=True,
        null=True,
        help_text="Optional photo — compressed automatically to save space.",
    )

    class Meta:
        ordering = ["-receipt_date", "-id"]

    def __str__(self) -> str:
        return self.production_lot_number or self.receipt_number

    def calculate_fields(self) -> None:
        self.metre_difference = self.vendor_metres - self.factory_measured_metres
        self.weight_difference = parse_text_decimal(self.vendor_weight) - parse_text_decimal(
            self.factory_measured_weight
        )
        self.accepted_metres = self.factory_measured_metres - self.rejected_metres

    def clean(self) -> None:
        self.calculate_fields()
        # Keep internal receipt_number aligned with lot / palli number.
        if self.production_lot_number and not self.receipt_number:
            self.receipt_number = self.production_lot_number
        if self.number_of_rolls < 0:
            raise ValidationError({"number_of_rolls": "Party thaan cannot be negative."})
        if self.factory_number_of_rolls < 0:
            raise ValidationError(
                {"factory_number_of_rolls": "Factory thaan cannot be negative."}
            )
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
