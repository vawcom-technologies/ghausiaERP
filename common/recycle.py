"""Recently-deleted (recycle bin) helpers for soft-deleted ERP records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.utils import timezone

from audit.models import AuditModel


@dataclass
class DeletedItem:
    module: str
    work_module: str
    label: str
    deleted_at: Any
    deleted_by: Any
    object: AuditModel
    restore_name: str
    model_key: str
    pending_request: Any = None


RECYCLE_REGISTRY: list[tuple[type[AuditModel], str, str, str, str]] = []


def register_recycle_model(
    model: type[AuditModel],
    module: str,
    restore_url_name: str,
    model_key: str,
    work_module: str,
) -> None:
    RECYCLE_REGISTRY.append((model, module, restore_url_name, model_key, work_module))


def soft_delete_record(obj: AuditModel, user) -> None:
    if not isinstance(obj, AuditModel):
        raise TypeError("Only AuditModel instances can be soft-deleted")
    obj.soft_delete(user)


def restore_record(obj: AuditModel, user) -> None:
    if not isinstance(obj, AuditModel):
        raise TypeError("Only AuditModel instances can be restored")
    obj.restore(user)
    from accounts.models import PermanentDeleteRequest

    PermanentDeleteRequest.objects.filter(
        model_key=_model_key_for(obj),
        object_pk=obj.pk,
        status=PermanentDeleteRequest.STATUS_PENDING,
    ).update(
        status=PermanentDeleteRequest.STATUS_REJECTED,
        review_note="Record was restored.",
        reviewed_at=timezone.now(),
    )


def _model_key_for(obj: AuditModel) -> str:
    _ensure_registry()
    for model, _module, _restore, model_key, _work in RECYCLE_REGISTRY:
        if isinstance(obj, model):
            return model_key
    return obj._meta.model_name


def list_recently_deleted(user=None, *, limit: int = 50) -> list[DeletedItem]:
    """Collect soft-deleted rows across registered models, newest first."""
    from accounts.models import PermanentDeleteRequest
    from accounts.permissions import assigned_modules, is_data_entry

    _ensure_registry()
    allowed = None
    if user is not None and is_data_entry(user):
        allowed = assigned_modules(user)

    pending = {
        (row.model_key, row.object_pk): row
        for row in PermanentDeleteRequest.objects.filter(status=PermanentDeleteRequest.STATUS_PENDING)
    }

    items: list[DeletedItem] = []
    for model, module, restore_name, model_key, work_module in RECYCLE_REGISTRY:
        if allowed is not None and work_module not in allowed:
            continue
        qs = model.objects.deleted().select_related("deleted_by").order_by("-deleted_at")[:limit]
        for obj in qs:
            items.append(
                DeletedItem(
                    module=module,
                    work_module=work_module,
                    label=str(obj),
                    deleted_at=obj.deleted_at,
                    deleted_by=obj.deleted_by,
                    object=obj,
                    restore_name=restore_name,
                    model_key=model_key,
                    pending_request=pending.get((model_key, obj.pk)),
                )
            )
    items.sort(key=lambda i: i.deleted_at or timezone.now(), reverse=True)
    return items[:limit]


def get_deleted_object(model_key: str, pk: int) -> AuditModel | None:
    _ensure_registry()
    for model, _module, _restore, key, _work in RECYCLE_REGISTRY:
        if key == model_key:
            return model.objects.deleted().filter(pk=pk).first()
    return None


def get_registry_row(model_key: str):
    _ensure_registry()
    for row in RECYCLE_REGISTRY:
        if row[3] == model_key:
            return row
    return None


def request_permanent_delete(user, model_key: str, pk: int):
    from accounts.models import PermanentDeleteRequest

    obj = get_deleted_object(model_key, pk)
    row = get_registry_row(model_key)
    if obj is None or row is None:
        return None
    existing = PermanentDeleteRequest.objects.filter(
        model_key=model_key,
        object_pk=pk,
        status=PermanentDeleteRequest.STATUS_PENDING,
    ).first()
    if existing:
        return existing
    return PermanentDeleteRequest.objects.create(
        model_key=model_key,
        object_pk=pk,
        module=row[1],
        label=str(obj),
        requested_by=user,
    )


def purge_deleted_object(model_key: str, pk: int) -> str | None:
    """Hard-delete a recycled row. Returns its label, or None if missing."""
    from production.models import (
        CalenderEntry,
        ComfortEntry,
        DyeingBatch,
        DyeingMaterialUsage,
        FinishedStock,
        Mixture,
        MixtureIngredient,
        ProcessMaterialUsage,
        ProductionLot,
        SingeingEntry,
        SixChamberEntry,
    )

    obj = get_deleted_object(model_key, pk)
    if obj is None:
        return None
    label = str(obj)

    with transaction.atomic():
        if model_key == "cloth_receipt":
            lot = (
                ProductionLot.all_objects.filter(cloth_receipt_id=obj.pk, is_deleted=True)
                .order_by("-deleted_at")
                .first()
            )
            if lot is not None:
                for batch in DyeingBatch.all_objects.filter(production_lot=lot):
                    DyeingMaterialUsage.all_objects.filter(dyeing_batch=batch).delete()
                    for mixture in Mixture.all_objects.filter(dyeing_batch=batch):
                        MixtureIngredient.all_objects.filter(mixture=mixture).delete()
                        mixture.delete()
                    batch.delete()
                for model in (
                    SingeingEntry,
                    SixChamberEntry,
                    CalenderEntry,
                    ComfortEntry,
                    FinishedStock,
                    ProcessMaterialUsage,
                ):
                    model.all_objects.filter(production_lot=lot).delete()
                lot.delete()
        obj.delete()
    return label


def _ensure_registry() -> None:
    if RECYCLE_REGISTRY:
        return
    from attendance.models import AttendanceRow
    from electricity.models import DailyElectricityReading, DailyPowerReading
    from fuel.models import OilBoilerShiftRecord, SteamBoilerShiftRecord
    from gate_entry.models import GateEntry
    from inventory.models import ChemicalIssueSlip, ChemicalStock, MaterialTransaction
    from maintenance.models import MaintenanceJob, MaintenanceMaterialUsage
    from production.models import (
        CalenderEntry,
        ComfortEntry,
        DyeingBatch,
        DyeingMaterialUsage,
        FinishedStock,
        Mixture,
        MixtureIngredient,
        ProcessMaterialUsage,
        ProductionLot,
        SingeingEntry,
        SixChamberEntry,
    )
    from receiving.models import ClothReceipt

    register = register_recycle_model
    restore = "accounts:restore_deleted"
    register(GateEntry, "Gate Entry", restore, "gate_entry", "gate_entry")
    register(ClothReceipt, "Cloth Receiving", restore, "cloth_receipt", "receiving")
    register(ProductionLot, "Production Lots", restore, "production_lot", "production_lots")
    register(SingeingEntry, "Singeing", restore, "singeing", "singeing")
    register(DyeingBatch, "Dyeing", restore, "dyeing_batch", "dyeing")
    register(DyeingMaterialUsage, "Dyeing Materials", restore, "dyeing_material", "dyeing")
    register(Mixture, "Mixtures", restore, "mixture", "dyeing")
    register(MixtureIngredient, "Mixture Ingredients", restore, "mixture_ingredient", "dyeing")
    register(SixChamberEntry, "Six Chamber", restore, "sixchamber", "six_chamber")
    register(CalenderEntry, "Calender", restore, "calender", "calender")
    register(ComfortEntry, "Comfort", restore, "comfort", "comfort")
    register(FinishedStock, "Finished Stock", restore, "finished_stock", "finished_stock")
    register(ProcessMaterialUsage, "Process Materials", restore, "process_material", "production_lots")
    register(MaterialTransaction, "Inventory", restore, "material_transaction", "inventory")
    register(ChemicalIssueSlip, "Chemical Issue Slips", restore, "chemical_issue_slip", "chemicals")
    register(ChemicalStock, "Chemical Stock", restore, "chemical_stock", "chemicals")
    register(MaintenanceJob, "Maintenance", restore, "maintenance_job", "maintenance")
    register(MaintenanceMaterialUsage, "Maintenance Materials", restore, "maintenance_material", "maintenance")
    register(DailyElectricityReading, "Electricity", restore, "electricity_reading", "electricity")
    register(DailyPowerReading, "Electricity", restore, "electricity_daily", "electricity")
    register(SteamBoilerShiftRecord, "Fuel", restore, "fuel_steam", "fuel")
    register(OilBoilerShiftRecord, "Fuel", restore, "fuel_oil", "fuel")
    register(AttendanceRow, "Attendance", restore, "attendance_row", "attendance")
