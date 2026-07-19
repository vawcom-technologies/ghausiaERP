"""Material stock calculation and transaction services."""

import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from audit.services.numbering import generate_transaction_number
from inventory.models import MaterialTransaction

logger = logging.getLogger("erp.inventory")


def get_material_stock(material_id: int) -> Decimal:
    """Calculate current stock from non-cancelled transactions."""
    agg = MaterialTransaction.objects.filter(
        material_id=material_id, is_cancelled=False
    ).aggregate(
        total_in=Sum("quantity_in"),
        total_out=Sum("quantity_out"),
    )
    total_in = agg["total_in"] or Decimal("0")
    total_out = agg["total_out"] or Decimal("0")
    return total_in - total_out


def get_material_stock_display(material) -> str:
    """Return stock with unit for display."""
    stock = get_material_stock(material.id)
    return f"{stock} {material.unit}"


def validate_stock_available(material_id: int, quantity: Decimal, allow_override: bool = False) -> None:
    """Raise ValueError if insufficient stock."""
    if allow_override:
        return
    available = get_material_stock(material_id)
    if quantity > available:
        raise ValueError(
            f"Insufficient stock. Available: {available}, Requested: {quantity}"
        )


@transaction.atomic
def create_material_transaction(
    *,
    material,
    transaction_type: str,
    quantity_in: Decimal = Decimal("0"),
    quantity_out: Decimal = Decimal("0"),
    unit: str,
    user,
    transaction_date=None,
    dyeing_batch=None,
    mixture=None,
    maintenance_job=None,
    related_reference: str = "",
    remarks: str = "",
) -> MaterialTransaction:
    """Create a material transaction with audit fields."""
    if transaction_date is None:
        transaction_date = timezone.now().date()

    if quantity_out > 0 and transaction_type not in ("Reversal",):
        validate_stock_available(material.id, quantity_out)

    mtx = MaterialTransaction(
        transaction_number=generate_transaction_number(),
        transaction_date=transaction_date,
        material=material,
        transaction_type=transaction_type,
        quantity_in=quantity_in,
        quantity_out=quantity_out,
        unit=unit,
        dyeing_batch=dyeing_batch,
        mixture=mixture,
        maintenance_job=maintenance_job,
        related_reference=related_reference,
        remarks=remarks,
        entered_by=user,
        created_by=user,
        updated_by=user,
    )
    mtx.full_clean()
    mtx.save()
    logger.info("Created material transaction %s type=%s", mtx.transaction_number, transaction_type)
    return mtx


@transaction.atomic
def reverse_material_transaction(original: MaterialTransaction, user, reason: str = "") -> MaterialTransaction:
    """Create a reversal transaction for a cancelled usage."""
    reversal = create_material_transaction(
        material=original.material,
        transaction_type="Reversal",
        quantity_in=original.quantity_out,
        quantity_out=original.quantity_in,
        unit=original.unit,
        user=user,
        transaction_date=timezone.now().date(),
        dyeing_batch=original.dyeing_batch,
        mixture=original.mixture,
        maintenance_job=original.maintenance_job,
        related_reference=f"Reversal of {original.transaction_number}",
        remarks=reason or f"Reversal of {original.transaction_number}",
    )
    reversal.reversed_transaction = original
    reversal.save(update_fields=["reversed_transaction"])
    return reversal


def get_materials_below_minimum():
    """Return materials where current stock is below minimum."""
    from master_data.models import Material

    below = []
    for material in Material.objects.filter(is_active=True):
        stock = get_material_stock(material.id)
        if stock < material.minimum_stock:
            below.append({"material": material, "stock": stock})
    return below
