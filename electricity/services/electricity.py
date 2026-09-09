"""Electricity reading services."""

from calendar import monthrange
from datetime import date
from decimal import Decimal

from electricity.models import DailyElectricityReading, DailyPowerReading

ZERO = Decimal("0")


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


def today_power_reading_exists(today: date | None = None) -> bool:
    from django.utils import timezone

    day = today or timezone.now().date()
    return DailyPowerReading.objects.filter(
        record_date=day, is_cancelled=False
    ).exists()


def parse_month_year(raw_month, raw_year, *, today: date | None = None) -> date:
    today = today or date.today()
    try:
        year = int(raw_year) if raw_year not in (None, "") else today.year
        month = int(raw_month) if raw_month not in (None, "") else today.month
    except (TypeError, ValueError):
        return date(today.year, today.month, 1)
    if month < 1 or month > 12:
        month = today.month
    if year < 2000 or year > 2100:
        year = today.year
    return date(year, month, 1)


def shift_month(month_start: date, delta_months: int) -> date:
    year = month_start.year
    month = month_start.month + delta_months
    while month < 1:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return date(year, month, 1)


def monthly_power_report(month_start: date) -> dict:
    last_day = monthrange(month_start.year, month_start.month)[1]
    start = month_start
    end = date(month_start.year, month_start.month, last_day)
    rows = list(
        DailyPowerReading.objects.filter(
            is_cancelled=False,
            record_date__gte=start,
            record_date__lte=end,
        ).order_by("record_date", "id")
    )

    cum_wapda_peak = ZERO
    cum_wapda_offpeak = ZERO
    cum_solar = ZERO
    cum_total = ZERO
    cum_peak_h = ZERO
    cum_offpeak_h = ZERO
    day_rows = []
    totals = {
        "wapda_peak_kwh": ZERO,
        "wapda_offpeak_kwh": ZERO,
        "wapda_total_kwh": ZERO,
        "solar_kwh": ZERO,
        "total_kwh": ZERO,
        "peak_hours": ZERO,
        "offpeak_hours": ZERO,
        "total_hours": ZERO,
    }

    for obj in rows:
        cum_wapda_peak += obj.wapda_peak_kwh
        cum_wapda_offpeak += obj.wapda_offpeak_kwh
        cum_solar += obj.solar_kwh
        cum_total += obj.total_kwh
        cum_peak_h += obj.peak_hours
        cum_offpeak_h += obj.offpeak_hours
        totals["wapda_peak_kwh"] += obj.wapda_peak_kwh
        totals["wapda_offpeak_kwh"] += obj.wapda_offpeak_kwh
        totals["wapda_total_kwh"] += obj.wapda_total_kwh
        totals["solar_kwh"] += obj.solar_kwh
        totals["total_kwh"] += obj.total_kwh
        totals["peak_hours"] += obj.peak_hours
        totals["offpeak_hours"] += obj.offpeak_hours
        totals["total_hours"] += obj.total_hours
        day_rows.append(
            {
                "object": obj,
                "record_date": obj.record_date,
                "source_mode": obj.get_source_mode_display(),
                "wapda_peak_kwh": obj.wapda_peak_kwh,
                "wapda_offpeak_kwh": obj.wapda_offpeak_kwh,
                "wapda_total_kwh": obj.wapda_total_kwh,
                "solar_kwh": obj.solar_kwh,
                "total_kwh": obj.total_kwh,
                "peak_hours": obj.peak_hours,
                "offpeak_hours": obj.offpeak_hours,
                "total_hours": obj.total_hours,
                "cum_wapda_peak_kwh": cum_wapda_peak,
                "cum_wapda_offpeak_kwh": cum_wapda_offpeak,
                "cum_wapda_kwh": cum_wapda_peak + cum_wapda_offpeak,
                "cum_solar_kwh": cum_solar,
                "cum_total_kwh": cum_total,
                "cum_peak_hours": cum_peak_h,
                "cum_offpeak_hours": cum_offpeak_h,
            }
        )

    return {"rows": day_rows, "totals": totals}
