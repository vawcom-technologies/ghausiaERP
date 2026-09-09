"""Fuel aggregation helpers (steam boiler monthly cumulative, etc.)."""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.db.models import Sum

from fuel.models import OilBoilerShiftRecord, SteamBoilerShiftRecord

ZERO = Decimal("0")


def parse_month_year(raw_month, raw_year, *, today: date | None = None) -> date:
    """Return the first day of the selected month (defaults to current month)."""
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


def month_bounds(month_start: date) -> tuple[date, date]:
    last_day = monthrange(month_start.year, month_start.month)[1]
    return month_start, date(month_start.year, month_start.month, last_day)


def shift_month(month_start: date, delta_months: int) -> date:
    """Move month_start by delta_months (can be negative)."""
    year = month_start.year
    month = month_start.month + delta_months
    while month < 1:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return date(year, month, 1)


def steam_boiler_monthly_cumulative(month_start: date) -> dict:
    """
    Aggregate active steam boiler shifts by date for one calendar month,
    with running (cumulative) Kuttal / Lunda qty and price totals.

    Raw shift rows stay in the DB forever; this only scopes the view.
    """
    start, end = month_bounds(month_start)
    rows = (
        SteamBoilerShiftRecord.objects.filter(
            is_cancelled=False,
            is_deleted=False,
            record_date__gte=start,
            record_date__lte=end,
        )
        .values("record_date")
        .annotate(
            kuttal_qty=Sum("kuttal_quantity"),
            kuttal_price_total=Sum("kuttal_daily_price"),
            lunda_qty=Sum("lunda_quantity"),
            lunda_price_total=Sum("lunda_daily_price"),
        )
        .order_by("record_date")
    )

    cum_k_qty = ZERO
    cum_k_price = ZERO
    cum_l_qty = ZERO
    cum_l_price = ZERO
    day_rows = []

    for row in rows:
        k_qty = row["kuttal_qty"] or ZERO
        k_price = row["kuttal_price_total"] or ZERO
        l_qty = row["lunda_qty"] or ZERO
        l_price = row["lunda_price_total"] or ZERO

        cum_k_qty += k_qty
        cum_k_price += k_price
        cum_l_qty += l_qty
        cum_l_price += l_price

        day_rows.append(
            {
                "record_date": row["record_date"],
                "kuttal_qty": k_qty,
                "kuttal_price_total": k_price,
                "lunda_qty": l_qty,
                "lunda_price_total": l_price,
                "cum_kuttal_qty": cum_k_qty,
                "cum_kuttal_price": cum_k_price,
                "cum_lunda_qty": cum_l_qty,
                "cum_lunda_price": cum_l_price,
                "cum_grand_price": cum_k_price + cum_l_price,
            }
        )

    return {
        "month_start": start,
        "month_end": end,
        "rows": day_rows,
        "totals": {
            "kuttal_qty": cum_k_qty,
            "kuttal_price": cum_k_price,
            "lunda_qty": cum_l_qty,
            "lunda_price": cum_l_price,
            "grand_price": cum_k_price + cum_l_price,
        },
    }


def oil_boiler_monthly_cumulative(month_start: date) -> dict:
    """
    Aggregate active oil boiler shifts by date for one calendar month,
    with running totals for run hours + Kuttal / Lunda / Fuel.
    """
    start, end = month_bounds(month_start)
    rows = (
        OilBoilerShiftRecord.objects.filter(
            is_cancelled=False,
            is_deleted=False,
            record_date__gte=start,
            record_date__lte=end,
        )
        .values("record_date")
        .annotate(
            run_hours=Sum("run_hours"),
            kuttal_qty=Sum("kuttal_quantity"),
            kuttal_price_total=Sum("kuttal_daily_price"),
            lunda_qty=Sum("lunda_quantity"),
            lunda_price_total=Sum("lunda_daily_price"),
            fuel_qty=Sum("fuel_quantity"),
            fuel_price_total=Sum("fuel_daily_price"),
        )
        .order_by("record_date")
    )

    cum_hours = ZERO
    cum_k_qty = ZERO
    cum_k_price = ZERO
    cum_l_qty = ZERO
    cum_l_price = ZERO
    cum_f_qty = ZERO
    cum_f_price = ZERO
    day_rows = []

    for row in rows:
        hours = row["run_hours"] or ZERO
        k_qty = row["kuttal_qty"] or ZERO
        k_price = row["kuttal_price_total"] or ZERO
        l_qty = row["lunda_qty"] or ZERO
        l_price = row["lunda_price_total"] or ZERO
        f_qty = row["fuel_qty"] or ZERO
        f_price = row["fuel_price_total"] or ZERO

        cum_hours += hours
        cum_k_qty += k_qty
        cum_k_price += k_price
        cum_l_qty += l_qty
        cum_l_price += l_price
        cum_f_qty += f_qty
        cum_f_price += f_price

        day_rows.append(
            {
                "record_date": row["record_date"],
                "run_hours": hours,
                "kuttal_qty": k_qty,
                "kuttal_price_total": k_price,
                "lunda_qty": l_qty,
                "lunda_price_total": l_price,
                "fuel_qty": f_qty,
                "fuel_price_total": f_price,
                "cum_run_hours": cum_hours,
                "cum_kuttal_qty": cum_k_qty,
                "cum_kuttal_price": cum_k_price,
                "cum_lunda_qty": cum_l_qty,
                "cum_lunda_price": cum_l_price,
                "cum_fuel_qty": cum_f_qty,
                "cum_fuel_price": cum_f_price,
                "cum_grand_price": cum_k_price + cum_l_price + cum_f_price,
            }
        )

    return {
        "month_start": start,
        "month_end": end,
        "rows": day_rows,
        "totals": {
            "run_hours": cum_hours,
            "kuttal_qty": cum_k_qty,
            "kuttal_price": cum_k_price,
            "lunda_qty": cum_l_qty,
            "lunda_price": cum_l_price,
            "fuel_qty": cum_f_qty,
            "fuel_price": cum_f_price,
            "grand_price": cum_k_price + cum_l_price + cum_f_price,
        },
    }
