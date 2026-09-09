from decimal import Decimal

from django.db import models

from audit.models import AuditModel


class SteamBoilerShiftRecord(AuditModel):
    """One daily shift record for steam boiler fuel (Kuttal + Lunda)."""

    SHIFT_1 = 1
    SHIFT_2 = 2
    SHIFT_CHOICES = [
        (SHIFT_1, "Shift 1"),
        (SHIFT_2, "Shift 2"),
    ]

    record_date = models.DateField("Date", db_index=True)
    shift = models.PositiveSmallIntegerField("Shift", choices=SHIFT_CHOICES)
    kuttal_quantity = models.DecimalField(
        "Kuttal Quantity", max_digits=12, decimal_places=3, default=Decimal("0")
    )
    kuttal_price = models.DecimalField(
        "Kuttal Price", max_digits=12, decimal_places=2, default=Decimal("0")
    )
    kuttal_daily_price = models.DecimalField(
        "Kuttal Daily Price", max_digits=14, decimal_places=2, default=Decimal("0")
    )
    lunda_quantity = models.DecimalField(
        "Lunda Quantity", max_digits=12, decimal_places=3, default=Decimal("0")
    )
    lunda_price = models.DecimalField(
        "Lunda Price", max_digits=12, decimal_places=2, default=Decimal("0")
    )
    lunda_daily_price = models.DecimalField(
        "Lunda Daily Price", max_digits=14, decimal_places=2, default=Decimal("0")
    )
    total_daily_price = models.DecimalField(
        "Total Daily Price", max_digits=14, decimal_places=2, default=Decimal("0")
    )
    remarks = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["-record_date", "shift", "-id"]
        verbose_name = "Steam Boiler Shift Record"
        verbose_name_plural = "Steam Boiler Shift Records"
        constraints = [
            models.UniqueConstraint(
                fields=["record_date", "shift"],
                condition=models.Q(is_deleted=False, is_cancelled=False),
                name="unique_active_steam_boiler_shift_per_day",
            )
        ]

    def __str__(self) -> str:
        return f"Steam {self.record_date} — Shift {self.shift}"

    def recalculate_daily_prices(self) -> None:
        kuttal_qty = self.kuttal_quantity or Decimal("0")
        kuttal_price = self.kuttal_price or Decimal("0")
        lunda_qty = self.lunda_quantity or Decimal("0")
        lunda_price = self.lunda_price or Decimal("0")
        self.kuttal_daily_price = (kuttal_qty * kuttal_price).quantize(Decimal("0.01"))
        self.lunda_daily_price = (lunda_qty * lunda_price).quantize(Decimal("0.01"))
        self.total_daily_price = (self.kuttal_daily_price + self.lunda_daily_price).quantize(
            Decimal("0.01")
        )

    def save(self, *args, **kwargs):
        self.recalculate_daily_prices()
        super().save(*args, **kwargs)


class OilBoilerShiftRecord(AuditModel):
    """One daily shift record for oil boiler (run time + Kuttal + Lunda + Fuel)."""

    SHIFT_1 = 1
    SHIFT_2 = 2
    SHIFT_CHOICES = [
        (SHIFT_1, "Shift 1"),
        (SHIFT_2, "Shift 2"),
    ]

    record_date = models.DateField("Date", db_index=True)
    shift = models.PositiveSmallIntegerField("Shift", choices=SHIFT_CHOICES)
    run_hours = models.DecimalField(
        "Run Time (hours)", max_digits=8, decimal_places=2, default=Decimal("0")
    )
    kuttal_quantity = models.DecimalField(
        "Kuttal Quantity", max_digits=12, decimal_places=3, default=Decimal("0")
    )
    kuttal_price = models.DecimalField(
        "Kuttal Price", max_digits=12, decimal_places=2, default=Decimal("0")
    )
    kuttal_daily_price = models.DecimalField(
        "Kuttal Daily Price", max_digits=14, decimal_places=2, default=Decimal("0")
    )
    lunda_quantity = models.DecimalField(
        "Lunda Quantity", max_digits=12, decimal_places=3, default=Decimal("0")
    )
    lunda_price = models.DecimalField(
        "Lunda Price", max_digits=12, decimal_places=2, default=Decimal("0")
    )
    lunda_daily_price = models.DecimalField(
        "Lunda Daily Price", max_digits=14, decimal_places=2, default=Decimal("0")
    )
    fuel_quantity = models.DecimalField(
        "Fuel Quantity", max_digits=12, decimal_places=3, default=Decimal("0")
    )
    fuel_price = models.DecimalField(
        "Fuel Price", max_digits=12, decimal_places=2, default=Decimal("0")
    )
    fuel_daily_price = models.DecimalField(
        "Fuel Daily Price", max_digits=14, decimal_places=2, default=Decimal("0")
    )
    total_daily_price = models.DecimalField(
        "Total Daily Price", max_digits=14, decimal_places=2, default=Decimal("0")
    )
    remarks = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["-record_date", "shift", "-id"]
        verbose_name = "Oil Boiler Shift Record"
        verbose_name_plural = "Oil Boiler Shift Records"
        constraints = [
            models.UniqueConstraint(
                fields=["record_date", "shift"],
                condition=models.Q(is_deleted=False, is_cancelled=False),
                name="unique_active_oil_boiler_shift_per_day",
            )
        ]

    def __str__(self) -> str:
        return f"Oil {self.record_date} — Shift {self.shift}"

    def recalculate_daily_prices(self) -> None:
        kuttal_qty = self.kuttal_quantity or Decimal("0")
        kuttal_price = self.kuttal_price or Decimal("0")
        lunda_qty = self.lunda_quantity or Decimal("0")
        lunda_price = self.lunda_price or Decimal("0")
        fuel_qty = self.fuel_quantity or Decimal("0")
        fuel_price = self.fuel_price or Decimal("0")
        self.kuttal_daily_price = (kuttal_qty * kuttal_price).quantize(Decimal("0.01"))
        self.lunda_daily_price = (lunda_qty * lunda_price).quantize(Decimal("0.01"))
        self.fuel_daily_price = (fuel_qty * fuel_price).quantize(Decimal("0.01"))
        self.total_daily_price = (
            self.kuttal_daily_price + self.lunda_daily_price + self.fuel_daily_price
        ).quantize(Decimal("0.01"))

    def save(self, *args, **kwargs):
        self.recalculate_daily_prices()
        super().save(*args, **kwargs)
