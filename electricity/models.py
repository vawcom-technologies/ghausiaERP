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
