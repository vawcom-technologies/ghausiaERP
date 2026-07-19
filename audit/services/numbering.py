"""Automatic document numbering service."""

from datetime import date

from django.db.models import Max


def _next_sequence(prefix: str, year: int, model, field: str, digits: int = 4) -> str:
    """Generate next sequential number for a given prefix and year."""
    pattern_start = f"{prefix}-{year}-"
    existing = (
        model.objects.filter(**{f"{field}__startswith": pattern_start})
        .aggregate(max_num=Max(field))
        .get("max_num")
    )
    if existing:
        try:
            seq = int(existing.split("-")[-1])
        except (ValueError, IndexError):
            seq = 0
    else:
        seq = 0
    return f"{prefix}-{year}-{seq + 1:0{digits}d}"


def generate_receipt_number() -> str:
    from receiving.models import ClothReceipt

    return _next_sequence("REC", date.today().year, ClothReceipt, "receipt_number")


def generate_lot_number() -> str:
    from production.models import ProductionLot

    return _next_sequence("LOT", date.today().year, ProductionLot, "lot_number")


def generate_batch_number(lot_number: str) -> str:
    from production.models import DyeingBatch

    prefix = f"{lot_number}-J"
    existing = (
        DyeingBatch.objects.filter(batch_number__startswith=prefix)
        .aggregate(max_num=Max("batch_number"))
        .get("max_num")
    )
    if existing:
        try:
            seq = int(existing.replace(prefix, ""))
        except ValueError:
            seq = 0
    else:
        seq = 0
    return f"{prefix}{seq + 1:02d}"


def generate_mixture_number() -> str:
    from production.models import Mixture

    return _next_sequence("MIX", date.today().year, Mixture, "mixture_number")


def generate_transaction_number() -> str:
    from inventory.models import MaterialTransaction

    return _next_sequence("MTX", date.today().year, MaterialTransaction, "transaction_number", digits=6)


def generate_maintenance_job_number() -> str:
    from maintenance.models import MaintenanceJob

    return _next_sequence("MNT", date.today().year, MaintenanceJob, "job_number")
