"""Bulk cloth receiving from spreadsheet grid or Excel import."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction
from django.db.models import Q

from audit.services.numbering import generate_lot_number
from master_data.models import ClothType, Vendor
from production.services.lot import create_production_lot_from_receipt
from receiving.models import ClothReceipt

RECEIVING_HEADERS = [
    "Lot Number / Palli Number",
    "Date",
    "Vendor",
    "Challan",
    "Cloth Type",
    "Rolls",
    "Vendor Metres",
    "Factory Metres",
    "Vendor Weight",
    "Factory Weight",
    "Rejected Metres",
    "Remarks",
]


def _to_decimal(value: Any, field_label: str) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_label} must be a number.") from exc


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


def _to_int(value: Any, field_label: str) -> int:
    if value is None or value == "":
        return 0
    try:
        return int(Decimal(str(value)))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_label} must be a whole number.") from exc


def resolve_vendor(name: str) -> Vendor:
    name = (name or "").strip()
    if not name:
        raise ValueError("Vendor is required.")
    existing = Vendor.objects.filter(Q(name__iexact=name)).first()
    if existing:
        if not existing.is_active:
            existing.is_active = True
            existing.save(update_fields=["is_active"])
        return existing
    return Vendor.objects.create(name=name, is_active=True)


def resolve_cloth_type(raw: str) -> ClothType:
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("Cloth Type is required.")
    ct = (
        ClothType.objects.filter(is_active=True)
        .filter(Q(name__iexact=raw) | Q(code__iexact=raw))
        .first()
    )
    if not ct and "(" in raw and raw.endswith(")"):
        code = raw.rsplit("(", 1)[-1].rstrip(")").strip()
        ct = ClothType.objects.filter(is_active=True, code__iexact=code).first()
    if not ct:
        raise ValueError(
            f"Cloth Type '{raw}' not found. Use an active cloth type name or code."
        )
    return ct


def row_is_blank(row: dict[str, Any]) -> bool:
    keys = (
        "Lot Number / Palli Number",
        "Vendor",
        "Challan",
        "Cloth Type",
        "Vendor Metres",
        "Factory Metres",
    )
    return all(not str(row.get(k) or "").strip() for k in keys)


@transaction.atomic
def save_receiving_row(row: dict[str, Any], user) -> ClothReceipt:
    """Create one cloth receipt + production lot from a spreadsheet row dict."""
    lot_number = str(row.get("Lot Number / Palli Number") or "").strip()
    if not lot_number:
        lot_number = generate_lot_number()

    if ClothReceipt.objects.filter(production_lot_number=lot_number).exists():
        raise ValueError(f"Lot / Palli Number '{lot_number}' already exists.")
    if ClothReceipt.objects.filter(receipt_number=lot_number).exists():
        raise ValueError(f"Lot / Palli Number '{lot_number}' already used.")

    vendor = resolve_vendor(str(row.get("Vendor") or ""))
    cloth_type = resolve_cloth_type(str(row.get("Cloth Type") or ""))
    challan = str(row.get("Challan") or "").strip()
    if not challan:
        raise ValueError("Challan is required.")

    factory_m = _to_decimal(row.get("Factory Metres"), "Factory Metres")
    rejected = _to_decimal(row.get("Rejected Metres"), "Rejected Metres")
    if rejected > factory_m:
        raise ValueError("Rejected metres cannot exceed factory metres.")

    receipt = ClothReceipt(
        receipt_number=lot_number,
        production_lot_number=lot_number,
        receipt_date=_to_date(row.get("Date")),
        vendor=vendor,
        vendor_challan_number=challan,
        cloth_type=cloth_type,
        number_of_rolls=_to_int(row.get("Rolls"), "Rolls"),
        vendor_metres=_to_decimal(row.get("Vendor Metres"), "Vendor Metres"),
        factory_measured_metres=factory_m,
        vendor_weight=_to_decimal(row.get("Vendor Weight"), "Vendor Weight"),
        factory_measured_weight=_to_decimal(row.get("Factory Weight"), "Factory Weight"),
        rejected_metres=rejected,
        remarks=str(row.get("Remarks") or "").strip(),
        created_by=user,
        updated_by=user,
    )
    receipt.calculate_fields()
    receipt.full_clean()
    receipt.save()
    create_production_lot_from_receipt(receipt, user)
    return receipt


def save_receiving_rows(rows: list[dict[str, Any]], user) -> tuple[int, list[str]]:
    """Save many rows. Returns (saved_count, error_messages)."""
    saved = 0
    errors: list[str] = []
    for idx, row in enumerate(rows, start=1):
        if row_is_blank(row):
            continue
        try:
            save_receiving_row(row, user)
            saved += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Row {idx}: {exc}")
    return saved, errors


def _getlist_at(post_data, key: str, i: int) -> str:
    values = post_data.getlist(key)
    return values[i] if i < len(values) else ""


def parse_grid_post(post_data) -> list[dict[str, Any]]:
    """Parse repeated POST arrays from the receiving sheet form."""
    lots = post_data.getlist("lot_number")
    rows = []
    for i in range(len(lots)):
        rows.append(
            {
                "Lot Number / Palli Number": _getlist_at(post_data, "lot_number", i),
                "Date": _getlist_at(post_data, "receipt_date", i),
                "Vendor": _getlist_at(post_data, "vendor_name", i),
                "Challan": _getlist_at(post_data, "challan", i),
                "Cloth Type": _getlist_at(post_data, "cloth_type", i),
                "Rolls": _getlist_at(post_data, "rolls", i),
                "Vendor Metres": _getlist_at(post_data, "vendor_metres", i),
                "Factory Metres": _getlist_at(post_data, "factory_metres", i),
                "Vendor Weight": _getlist_at(post_data, "vendor_weight", i),
                "Factory Weight": _getlist_at(post_data, "factory_weight", i),
                "Rejected Metres": _getlist_at(post_data, "rejected_metres", i),
                "Remarks": _getlist_at(post_data, "remarks", i),
            }
        )
    return rows
