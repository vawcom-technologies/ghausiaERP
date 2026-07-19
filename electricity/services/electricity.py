"""Electricity reading services."""

from decimal import Decimal

from electricity.models import DailyElectricityReading


def get_latest_closing_reading(meter_id: int) -> Decimal | None:
    """Get the latest non-cancelled closing reading for a meter."""
    reading = (
        DailyElectricityReading.objects.filter(meter_id=meter_id, is_cancelled=False)
        .order_by("-reading_date", "-id")
        .first()
    )
    return reading.closing_reading if reading else None


def calculate_units_consumed(opening: Decimal, closing: Decimal, multiplier: Decimal) -> Decimal:
    """Calculate units consumed from meter readings."""
    return (closing - opening) * multiplier


def today_readings_count() -> int:
    """Count active electricity readings entered today."""
    from django.utils import timezone

    today = timezone.now().date()
    return DailyElectricityReading.objects.filter(
        reading_date=today, is_cancelled=False
    ).count()


def active_meters_count() -> int:
    from electricity.models import ElectricityMeter

    return ElectricityMeter.objects.filter(is_active=True).count()
