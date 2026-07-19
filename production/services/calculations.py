"""Reusable calculation helpers for production stages."""

from decimal import Decimal
from typing import Optional


def safe_divide(numerator: Decimal, denominator: Decimal) -> Decimal:
    """Divide safely, returning zero when denominator is zero."""
    if denominator == 0:
        return Decimal("0")
    return numerator / denominator


def calculate_loss(input_metres: Decimal, output_metres: Decimal) -> tuple[Decimal, Decimal]:
    """
    Calculate loss metres and loss percentage.

    Returns (loss_metres, loss_percentage).
    """
    loss_metres = input_metres - output_metres
    loss_percentage = safe_divide(loss_metres, input_metres) * Decimal("100")
    return loss_metres, loss_percentage


def calculate_shrinkage(
    initial_metres: Decimal, final_metres: Decimal
) -> tuple[Decimal, Decimal]:
    """
    Calculate total metre loss and shrinkage percentage.

    Returns (total_loss, shrinkage_percentage).
    """
    total_loss = initial_metres - final_metres
    shrinkage_percentage = safe_divide(total_loss, initial_metres) * Decimal("100")
    return total_loss, shrinkage_percentage


def get_stage_summary(entries, input_field: str = "input_metres", output_field: str = "output_metres"):
    """Summarize active (non-cancelled) process entries."""
    active = [e for e in entries if not e.is_cancelled]
    if not active:
        return {
            "input_metres": Decimal("0"),
            "output_metres": Decimal("0"),
            "loss_metres": Decimal("0"),
            "loss_percentage": Decimal("0"),
            "count": 0,
        }
    input_total = sum(getattr(e, input_field) for e in active)
    output_total = sum(getattr(e, output_field) for e in active)
    loss, pct = calculate_loss(input_total, output_total)
    return {
        "input_metres": input_total,
        "output_metres": output_total,
        "loss_metres": loss,
        "loss_percentage": pct,
        "count": len(active),
    }
