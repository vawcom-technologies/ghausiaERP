from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from audit.models import AuditModel
from master_data.models import Machine


class ElectricityMeter(models.Model):
    name = models.CharField(max_length=200)
    meter_number = models.CharField(max_length=100, unique=True)
    department = models.CharField(max_length=100)
    machine = models.ForeignKey(
        Machine, on_delete=models.SET_NULL, null=True, blank=True, related_name="electricity_meters"
    )
    multiplier = models.DecimalField(max_digits=8, decimal_places=3, default=Decimal("1"))
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.meter_number})"


class DailyElectricityReading(AuditModel):
    reading_date = models.DateField()
    meter = models.ForeignKey(
        ElectricityMeter, on_delete=models.PROTECT, related_name="readings"
    )
    opening_reading = models.DecimalField(max_digits=12, decimal_places=3)
    closing_reading = models.DecimalField(max_digits=12, decimal_places=3)
    multiplier = models.DecimalField(max_digits=8, decimal_places=3)
    units_consumed = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="electricity_readings_entered",
        null=True,
        blank=True,
    )
    checked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="electricity_readings_checked",
        null=True,
        blank=True,
    )
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ["-reading_date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["reading_date", "meter"],
                condition=models.Q(is_cancelled=False),
                name="unique_active_reading_per_meter_date",
            )
        ]

    def __str__(self) -> str:
        return f"{self.meter.name} - {self.reading_date}"

    def calculate_units(self) -> None:
        self.units_consumed = (self.closing_reading - self.opening_reading) * self.multiplier

    def clean(self) -> None:
        if self.multiplier <= 0:
            raise ValidationError({"multiplier": "Multiplier must be greater than zero."})
        if self.closing_reading < self.opening_reading:
            raise ValidationError(
                {"closing_reading": "Closing reading cannot be lower than opening reading."}
            )
        self.calculate_units()

    def save(self, *args, **kwargs):
        self.calculate_units()
        super().save(*args, **kwargs)


class DailyPowerReading(AuditModel):
    """One factory electricity register row per day: WAPDA and optional solar."""

    MODE_WAPDA = "wapda"
    MODE_WAPDA_SOLAR = "wapda_solar"
    MODE_CHOICES = (
        (MODE_WAPDA, "WAPDA only"),
        (MODE_WAPDA_SOLAR, "WAPDA + Solar"),
    )

    record_date = models.DateField()
    source_mode = models.CharField(max_length=20, choices=MODE_CHOICES, default=MODE_WAPDA)
    wapda_peak_kwh = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    wapda_offpeak_kwh = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    solar_kwh = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    peak_hours = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0"))
    offpeak_hours = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0"))
    wapda_total_kwh = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    total_kwh = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    total_hours = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0"))
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ["-record_date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["record_date"],
                condition=models.Q(is_cancelled=False, is_deleted=False),
                name="unique_active_power_reading_per_date",
            )
        ]

    def __str__(self) -> str:
        return f"Electricity {self.record_date}"

    @property
    def includes_solar(self) -> bool:
        return self.source_mode == self.MODE_WAPDA_SOLAR

    def calculate_totals(self) -> None:
        if self.source_mode != self.MODE_WAPDA_SOLAR:
            self.solar_kwh = Decimal("0")
        peak = self.wapda_peak_kwh or Decimal("0")
        offpeak = self.wapda_offpeak_kwh or Decimal("0")
        solar = self.solar_kwh or Decimal("0")
        peak_h = self.peak_hours or Decimal("0")
        offpeak_h = self.offpeak_hours or Decimal("0")
        self.wapda_total_kwh = peak + offpeak
        self.total_kwh = self.wapda_total_kwh + solar
        self.total_hours = peak_h + offpeak_h

    def clean(self) -> None:
        for field in (
            "wapda_peak_kwh",
            "wapda_offpeak_kwh",
            "solar_kwh",
            "peak_hours",
            "offpeak_hours",
        ):
            value = getattr(self, field) or Decimal("0")
            if value < 0:
                raise ValidationError({field: "Value cannot be negative."})
        if self.peak_hours and self.peak_hours > Decimal("24"):
            raise ValidationError({"peak_hours": "Peak hours cannot be more than 24."})
        if self.offpeak_hours and self.offpeak_hours > Decimal("24"):
            raise ValidationError({"offpeak_hours": "Non-peak hours cannot be more than 24."})
        if (self.peak_hours or Decimal("0")) + (self.offpeak_hours or Decimal("0")) > Decimal("24"):
            raise ValidationError("Peak and non-peak hours together cannot be more than 24.")
        self.calculate_totals()

    def save(self, *args, **kwargs):
        self.calculate_totals()
        super().save(*args, **kwargs)
