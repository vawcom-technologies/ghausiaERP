"""Bulk material purchase from spreadsheet grid or Excel import."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction
from django.db.models import Q

from inventory.services.stock import create_material_transaction
from master_data.models import Material

PURCHASE_HEADERS = [
    "Date",
    "Material",
    "Quantity In",
    "Unit",
    "Reference",
    "Remarks",
]


def _to_decimal(value: Any, field_label: str) -> Decimal:
    if value is None or value == "":
        raise ValueError(f"{field_label} is required.")
    try:
        qty = Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_label} must be a number.") from exc
    if qty <= 0:
        raise ValueError(f"{field_label} must be greater than zero.")
    return qty


def _to_date(value: Any) -> date:
    if value is None or value == "":
        return date.today()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Invalid date '{text}'. Use YYYY-MM-DD.")


def resolve_material(raw: str) -> Material:
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("Material is required.")
    mat = (
        Material.objects.filter(is_active=True)
        .filter(Q(name__iexact=raw) | Q(code__iexact=raw))
        .first()
    )
    if not mat and "(" in raw and raw.endswith(")"):
        code = raw.rsplit("(", 1)[-1].rstrip(")").strip()
        mat = Material.objects.filter(is_active=True, code__iexact=code).first()
    if not mat:
        raise ValueError(f"Material '{raw}' not found. Use an active material name or code.")
    return mat


def row_is_blank(row: dict[str, Any]) -> bool:
    keys = ("Material", "Quantity In")
    return all(not str(row.get(k) or "").strip() for k in keys)


@transaction.atomic
def save_purchase_row(row: dict[str, Any], user):
    material = resolve_material(str(row.get("Material") or ""))
    qty = _to_decimal(row.get("Quantity In"), "Quantity In")
    unit = str(row.get("Unit") or "").strip() or material.unit
    return create_material_transaction(
        material=material,
        transaction_type="Purchase",
        quantity_in=qty,
        quantity_out=Decimal("0"),
        unit=unit,
        user=user,
        transaction_date=_to_date(row.get("Date")),
        related_reference=str(row.get("Reference") or "").strip(),
        remarks=str(row.get("Remarks") or "").strip(),
    )


def save_purchase_rows(rows: list[dict[str, Any]], user) -> tuple[int, list[str]]:
    saved = 0
    errors: list[str] = []
    for idx, row in enumerate(rows, start=1):
        if row_is_blank(row):
            continue
        try:
            save_purchase_row(row, user)
            saved += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Row {idx}: {exc}")
    return saved, errors


def _getlist_at(post_data, key: str, i: int) -> str:
    values = post_data.getlist(key)
    return values[i] if i < len(values) else ""


def parse_purchase_grid_post(post_data) -> list[dict[str, Any]]:
    materials = post_data.getlist("material")
    rows = []
    for i in range(len(materials)):
        rows.append(
            {
                "Date": _getlist_at(post_data, "transaction_date", i),
                "Material": _getlist_at(post_data, "material", i),
                "Quantity In": _getlist_at(post_data, "quantity_in", i),
                "Unit": _getlist_at(post_data, "unit", i),
                "Reference": _getlist_at(post_data, "reference", i),
                "Remarks": _getlist_at(post_data, "remarks", i),
            }
        )
    return rows
