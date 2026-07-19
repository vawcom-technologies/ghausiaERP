"""Production lot update services."""

import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

logger = logging.getLogger("erp.production")


@transaction.atomic
def create_production_lot_from_receipt(receipt, user) -> "ProductionLot":
    """Create a production lot when cloth is received."""
    from production.models import ProductionLot

    from receiving.models import parse_text_decimal

    weight = parse_text_decimal(receipt.factory_measured_weight)
    lot = ProductionLot(
        lot_number=receipt.production_lot_number,
        cloth_receipt=receipt,
        vendor=receipt.vendor,
        cloth_type=receipt.cloth_type,
        initial_metres=receipt.accepted_metres,
        initial_weight=weight,
        current_metres=receipt.accepted_metres,
        current_weight=weight,
        current_stage="Receiving",
        status="Received",
        start_date=receipt.receipt_date,
        created_by=user,
        updated_by=user,
    )
    lot.save()
    logger.info("Created production lot %s from receipt %s", lot.lot_number, receipt.receipt_number)
    return lot


@transaction.atomic
def update_lot_after_singeing(entry, user) -> None:
    """Update production lot after singeing entry."""
    lot = entry.production_lot
    lot.current_metres = entry.output_metres
    lot.current_weight = entry.output_weight
    lot.current_stage = "Dyeing"
    lot.status = "In Production"
    lot.updated_by = user
    lot.save()
    logger.info("Lot %s moved to Dyeing after singeing", lot.lot_number)


@transaction.atomic
def complete_dyeing_stage(lot, user) -> None:
    """Complete dyeing stage and move lot to Six Chamber."""
    from production.models import DyeingBatch

    batches = DyeingBatch.objects.filter(production_lot=lot, is_cancelled=False)
    output_metres = batches.aggregate(total=Sum("output_metres"))["total"] or Decimal("0")
    output_weight = batches.aggregate(total=Sum("output_weight"))["total"] or Decimal("0")

    lot.current_metres = output_metres
    lot.current_weight = output_weight
    lot.current_stage = "Six Chamber"
    lot.dyeing_completed = True
    lot.updated_by = user
    lot.save()
    logger.info("Lot %s dyeing completed, moved to Six Chamber", lot.lot_number)


@transaction.atomic
def update_lot_after_six_chamber(entry, user) -> None:
    lot = entry.production_lot
    lot.current_metres = entry.output_metres
    lot.current_weight = entry.output_weight
    lot.current_stage = "Calender"
    lot.updated_by = user
    lot.save()


@transaction.atomic
def update_lot_after_calender(entry, user) -> None:
    lot = entry.production_lot
    lot.current_metres = entry.output_metres
    lot.current_weight = entry.output_weight
    lot.current_stage = "Comfort"
    lot.updated_by = user
    lot.save()


@transaction.atomic
def update_lot_after_comfort(entry, user) -> None:
    lot = entry.production_lot
    lot.current_metres = entry.output_metres
    lot.current_weight = entry.output_weight
    lot.current_stage = "Finished"
    lot.updated_by = user
    lot.save()


@transaction.atomic
def complete_finished_stock(finished_stock, user) -> None:
    """Complete production lot when finished stock is saved."""
    lot = finished_stock.production_lot
    lot.current_metres = finished_stock.final_metres
    lot.current_weight = finished_stock.final_weight
    lot.current_stage = "Finished"
    lot.status = "Completed"
    lot.completion_date = finished_stock.completion_date
    lot.updated_by = user
    lot.save()
    logger.info("Lot %s completed with finished stock", lot.lot_number)


def get_lot_detail_context(lot) -> dict:
    """Build context data for production lot detail page."""
    from production.models import DyeingBatch, DyeingMaterialUsage, FinishedStock
    from production.services.calculations import calculate_shrinkage, get_stage_summary

    singeing = get_stage_summary(lot.singeing_entries.all())
    dyeing_batches = [b for b in lot.dyeing_batches.all() if not b.is_cancelled]
    dyeing_input = sum(b.input_metres for b in dyeing_batches) if dyeing_batches else Decimal("0")
    dyeing_output = sum(b.output_metres for b in dyeing_batches) if dyeing_batches else Decimal("0")
    from production.services.calculations import calculate_loss

    dyeing_loss, dyeing_loss_pct = calculate_loss(dyeing_input, dyeing_output)
    six_chamber = get_stage_summary(lot.six_chamber_entries.all())
    calender = get_stage_summary(lot.calender_entries.all())
    comfort = get_stage_summary(lot.comfort_entries.all())

    dyeing_materials = DyeingMaterialUsage.objects.filter(
        dyeing_batch__production_lot=lot, is_cancelled=False
    ).select_related("material", "dyeing_batch")

    finished = None
    total_loss = Decimal("0")
    shrinkage = Decimal("0")
    try:
        finished = lot.finished_stock
        if finished and not finished.is_cancelled:
            total_loss, shrinkage = calculate_shrinkage(lot.initial_metres, finished.final_metres)
    except FinishedStock.DoesNotExist:
        total_loss = lot.initial_metres - lot.current_metres
        from production.services.calculations import safe_divide

        shrinkage = safe_divide(total_loss, lot.initial_metres) * Decimal("100")

    return {
        "singeing": singeing,
        "dyeing": {
            "input_metres": dyeing_input,
            "output_metres": dyeing_output,
            "loss_metres": dyeing_loss,
            "loss_percentage": dyeing_loss_pct,
            "count": len(dyeing_batches),
            "batches": dyeing_batches,
        },
        "six_chamber": six_chamber,
        "calender": calender,
        "comfort": comfort,
        "dyeing_materials": dyeing_materials,
        "finished_stock": finished if finished and not finished.is_cancelled else None,
        "total_metre_loss": total_loss,
        "shrinkage_percentage": shrinkage,
    }
