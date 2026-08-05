"""Recently-deleted (recycle bin) helpers for soft-deleted ERP records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from audit.models import AuditModel


@dataclass
class DeletedItem:
    module: str
    label: str
    deleted_at: Any
    deleted_by: Any
    object: AuditModel
    restore_name: str  # url name
    model_key: str


# Models registered for the profile recycle bin (label, module, restore url name)
RECYCLE_REGISTRY: list[tuple[type[AuditModel], str, str, str]] = []


def register_recycle_model(model: type[AuditModel], module: str, restore_url_name: str, model_key: str) -> None:
    RECYCLE_REGISTRY.append((model, module, restore_url_name, model_key))


def soft_delete_record(obj: AuditModel, user) -> None:
    if not isinstance(obj, AuditModel):
        raise TypeError("Only AuditModel instances can be soft-deleted")
    obj.soft_delete(user)


def restore_record(obj: AuditModel, user) -> None:
    if not isinstance(obj, AuditModel):
        raise TypeError("Only AuditModel instances can be restored")
    obj.restore(user)


def list_recently_deleted(*, limit: int = 50) -> list[DeletedItem]:
    """Collect soft-deleted rows across registered models, newest first."""
    # Lazy registry fill to avoid import cycles at module load
    _ensure_registry()
    items: list[DeletedItem] = []
    for model, module, restore_name, model_key in RECYCLE_REGISTRY:
        qs = model.objects.deleted().select_related("deleted_by").order_by("-deleted_at")[:limit]
        for obj in qs:
            items.append(
                DeletedItem(
                    module=module,
                    label=str(obj),
                    deleted_at=obj.deleted_at,
                    deleted_by=obj.deleted_by,
                    object=obj,
                    restore_name=restore_name,
                    model_key=model_key,
                )
            )
    items.sort(key=lambda i: i.deleted_at or timezone.now(), reverse=True)
    return items[:limit]


def get_deleted_object(model_key: str, pk: int) -> AuditModel | None:
    _ensure_registry()
    for model, _module, _restore, key in RECYCLE_REGISTRY:
        if key == model_key:
            return model.objects.deleted().filter(pk=pk).first()
    return None


def _ensure_registry() -> None:
    if RECYCLE_REGISTRY:
        return
    from gate_entry.models import GateEntry
    from receiving.models import ClothReceipt

    register_recycle_model(GateEntry, "Gate Entry", "accounts:restore_deleted", "gate_entry")
    register_recycle_model(ClothReceipt, "Cloth Receiving", "accounts:restore_deleted", "cloth_receipt")
