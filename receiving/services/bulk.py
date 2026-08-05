"""Bulk cloth receiving from spreadsheet grid or Excel import."""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.db.models import Q

from common.images import compress_image_upload
from master_data.models import ClothType, Vendor
from production.services.lot import create_production_lot_from_receipt
from receiving.models import ClothReceipt

RECEIVING_HEADERS = [
    "Lot Number / Palli Number",
    "Date",
    "Party",
    "PV blend",
    "Read Pick",
    "Party Thaan",
    "Factory Thaan",
    "Vendor Metres",
    "Factory Metres",
    "Vendor Weight",
    "Factory Weight",
    "Remarks",
]

_TEMP_TOKEN_RE = re.compile(r"^[a-f0-9]{32}$")


def receipt_to_excel_row(receipt: ClothReceipt) -> list[Any]:
    """Map a saved receipt to RECEIVING_HEADERS values for Excel export."""
    return [
        receipt.production_lot_number or "",
        receipt.receipt_date.isoformat() if receipt.receipt_date else "",
        receipt.vendor.name if receipt.vendor_id else "",
        receipt.pv_blend_qty or "",
        receipt.read_pick_qty or "",
        receipt.number_of_rolls,
        receipt.factory_number_of_rolls,
        str(receipt.vendor_metres) if receipt.vendor_metres is not None else "",
        str(receipt.factory_measured_metres)
        if receipt.factory_measured_metres is not None
        else "",
        receipt.vendor_weight or "",
        receipt.factory_measured_weight or "",
        receipt.remarks or "",
    ]


def _temp_image_dir() -> Path:
    path = Path(settings.MEDIA_ROOT) / "receiving" / "tmp"
    path.mkdir(parents=True, exist_ok=True)
    return path


def persist_temp_image(uploaded_file) -> str:
    """Store an upload under media/receiving/tmp and return a 32-char token."""
    token = uuid.uuid4().hex
    prepared = compress_image_upload(uploaded_file)
    dest = _temp_image_dir() / f"{token}.jpg"
    with dest.open("wb") as out:
        if hasattr(prepared, "chunks"):
            for chunk in prepared.chunks():
                out.write(chunk)
        else:
            out.write(prepared.read())
    return token


def load_temp_image(token: str):
    """Reload a previously stashed sheet photo as an upload."""
    token = (token or "").strip()
    if not _TEMP_TOKEN_RE.match(token):
        return None
    path = _temp_image_dir() / f"{token}.jpg"
    if not path.is_file():
        return None
    return SimpleUploadedFile(f"{token}.jpg", path.read_bytes(), content_type="image/jpeg")


def clear_temp_image(token: str) -> None:
    token = (token or "").strip()
    if not _TEMP_TOKEN_RE.match(token):
        return
    path = _temp_image_dir() / f"{token}.jpg"
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def temp_image_url(token: str) -> str:
    token = (token or "").strip()
    if not _TEMP_TOKEN_RE.match(token):
        return ""
    base = settings.MEDIA_URL if settings.MEDIA_URL.endswith("/") else f"{settings.MEDIA_URL}/"
    return f"{base}receiving/tmp/{token}.jpg"


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
        raise ValueError("Party is required.")
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


def normalize_cloth_qty(value: Any) -> str:
    """Normalize cloth-type cell text. Lone '/' means empty."""
    text = str(value or "").strip()
    if text in {"/", "-", "—"}:
        return ""
    return text


def cloth_qty_meaningful(value: Any) -> bool:
    """True when the cell has a real value (not blank / lone slash)."""
    return bool(normalize_cloth_qty(value))


def parse_cloth_type_quantities(row: dict[str, Any]) -> tuple[str, str]:
    """Read PV blend / Read Pick text values (slash and codes allowed)."""
    return (
        normalize_cloth_qty(row.get("PV blend")),
        normalize_cloth_qty(row.get("Read Pick")),
    )


def resolve_cloth_type_from_row(row: dict[str, Any]) -> ClothType:
    """
    Resolve primary cloth type from PV blend / Read Pick cells.

    Both may be filled (numbers, codes, or values with /). Primary type is Read
    Pick only when PV blend is empty; otherwise PV blend.
    """
    legacy = str(row.get("Cloth Type") or "").strip()
    pv, rp = parse_cloth_type_quantities(row)

    if not cloth_qty_meaningful(pv) and not cloth_qty_meaningful(rp):
        if legacy:
            return resolve_cloth_type(legacy)
        raise ValueError("Cloth Type is required. Enter PV blend and/or Read Pick.")
    if cloth_qty_meaningful(rp) and not cloth_qty_meaningful(pv):
        return resolve_cloth_type("Read Pick")
    return resolve_cloth_type("PV blend")


def row_is_blank(row: dict[str, Any]) -> bool:
    """True when the row has no real user data (date/zero defaults alone don't count)."""
    text_keys = (
        "Lot Number / Palli Number",
        "Party",
        "PV blend",
        "Read Pick",
        "Cloth Type",
        "Vendor Metres",
        "Factory Metres",
        "Remarks",
    )
    no_text = all(not str(row.get(k) or "").strip() for k in text_keys)
    no_image = not row.get("_image")
    # Ignore default zeros on numeric sheet fields when deciding blankness.
    numeric_defaults = ("0", "0.0", "0.00", "0.000")
    meaningful_numbers = any(
        str(row.get(k) or "").strip() not in ("", *numeric_defaults)
        for k in (
            "Party Thaan",
            "Factory Thaan",
            "Vendor Metres",
            "Factory Metres",
            "Vendor Weight",
            "Factory Weight",
        )
    )
    return no_text and no_image and not meaningful_numbers


def _row_get(row: dict[str, Any], *keys: str) -> Any:
    """Return the first non-empty value among alternate column keys."""
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip() != "":
            return value
    return row.get(keys[0])


def _require_text(row: dict[str, Any], key: str, label: str, missing: list[str]) -> str:
    value = str(row.get(key) or "").strip()
    if not value:
        missing.append(label)
    return value


def _require_positive_decimal(
    row: dict[str, Any], key: str, label: str, missing: list[str]
) -> Decimal | None:
    raw = str(row.get(key) or "").strip()
    if not raw:
        missing.append(label)
        return None
    try:
        value = _to_decimal(raw, label)
    except ValueError:
        missing.append(f"{label} (invalid number)")
        return None
    if value <= 0:
        missing.append(f"{label} (must be greater than 0)")
        return None
    return value


def _require_non_negative_int(
    row: dict[str, Any], key: str, label: str, missing: list[str]
) -> int | None:
    raw = str(row.get(key) or "").strip()
    if raw == "":
        missing.append(label)
        return None
    try:
        value = _to_int(raw, label)
    except ValueError:
        missing.append(f"{label} (invalid number)")
        return None
    if value < 0:
        missing.append(f"{label} (cannot be negative)")
        return None
    if value == 0:
        missing.append(f"{label} (must be greater than 0)")
        return None
    return value


def validate_row_complete(row: dict[str, Any]) -> list[str]:
    """Return human-readable missing/invalid field labels. Empty list means ready to save."""
    missing: list[str] = []
    _require_text(row, "Lot Number / Palli Number", "Lot / Palli Number", missing)

    date_raw = str(row.get("Date") or "").strip()
    if not date_raw:
        missing.append("Date")
    else:
        try:
            _to_date(date_raw)
        except ValueError:
            missing.append("Date (invalid)")

    _require_text(row, "Party", "Party", missing)

    legacy = str(row.get("Cloth Type") or "").strip()
    pv_raw = normalize_cloth_qty(row.get("PV blend"))
    rp_raw = normalize_cloth_qty(row.get("Read Pick"))
    if not cloth_qty_meaningful(pv_raw) and not cloth_qty_meaningful(rp_raw) and not legacy:
        missing.append("Cloth Type (enter PV blend and/or Read Pick; use / if empty)")

    if str(row.get("Party Thaan") or "").strip() != "":
        _require_non_negative_int(row, "Party Thaan", "Party Thaan", missing)
    else:
        _require_non_negative_int(row, "Rolls", "Party Thaan", missing)
    _require_non_negative_int(row, "Factory Thaan", "Factory Thaan", missing)
    _require_positive_decimal(row, "Vendor Metres", "Vendor M", missing)
    _require_positive_decimal(row, "Factory Metres", "Factory M", missing)

    return missing


@transaction.atomic
def save_receiving_row(row: dict[str, Any], user) -> ClothReceipt:
    """Create one cloth receipt + production lot from a spreadsheet row dict."""
    problems = validate_row_complete(row)
    if problems:
        raise ValueError("Incomplete row — fill: " + ", ".join(problems))

    lot_number = str(row.get("Lot Number / Palli Number") or "").strip()

    if ClothReceipt.all_objects.filter(production_lot_number=lot_number).exists():
        raise ValueError(f"Lot / Palli Number '{lot_number}' already exists.")
    if ClothReceipt.all_objects.filter(receipt_number=lot_number).exists():
        raise ValueError(f"Lot / Palli Number '{lot_number}' already used.")

    vendor = resolve_vendor(str(_row_get(row, "Party", "Vendor") or ""))
    cloth_type = resolve_cloth_type_from_row(row)
    pv_qty, rp_qty = parse_cloth_type_quantities(row)
    challan = str(row.get("Challan") or "").strip()

    factory_m = _to_decimal(row.get("Factory Metres"), "Factory M")
    image = row.get("_image")
    prepared_image = compress_image_upload(image) if image else None

    receipt = ClothReceipt(
        receipt_number=lot_number,
        production_lot_number=lot_number,
        receipt_date=_to_date(row.get("Date")),
        vendor=vendor,
        vendor_challan_number=challan,
        cloth_type=cloth_type,
        pv_blend_qty=pv_qty,
        read_pick_qty=rp_qty,
        number_of_rolls=_to_int(
            _row_get(row, "Party Thaan", "Rolls"), "Party Thaan"
        ),
        factory_number_of_rolls=_to_int(
            _row_get(row, "Factory Thaan"), "Factory Thaan"
        ),
        vendor_metres=_to_decimal(row.get("Vendor Metres"), "Vendor M"),
        factory_measured_metres=factory_m,
        vendor_weight=normalize_cloth_qty(row.get("Vendor Weight")),
        factory_measured_weight=normalize_cloth_qty(row.get("Factory Weight")),
        rejected_metres=Decimal("0"),
        remarks=str(row.get("Remarks") or "").strip(),
        created_by=user,
        updated_by=user,
    )
    receipt.calculate_fields()
    receipt.full_clean(exclude=["receipt_image"])
    if prepared_image:
        filename = getattr(prepared_image, "name", None) or "receipt.jpg"
        receipt.receipt_image.save(filename, prepared_image, save=False)
    receipt.save()
    clear_temp_image(str(row.get("_image_token") or ""))
    create_production_lot_from_receipt(receipt, user)
    return receipt


def save_receiving_rows(rows: list[dict[str, Any]], user) -> tuple[int, list[str], list[int]]:
    """
    Save complete rows only.

    Returns (saved_count, error_messages, failed_row_indexes_0_based).
    Incomplete / invalid rows are not written to the database.
    """
    saved = 0
    errors: list[str] = []
    failed_indexes: list[int] = []
    for idx, row in enumerate(rows):
        row_no = idx + 1
        if row_is_blank(row):
            continue
        problems = validate_row_complete(row)
        if problems:
            errors.append(f"Row {row_no}: not saved — fill: {', '.join(problems)}")
            failed_indexes.append(idx)
            continue
        try:
            save_receiving_row(row, user)
            saved += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Row {row_no}: {exc}")
            failed_indexes.append(idx)
    return saved, errors, failed_indexes


def sheet_display_rows(
    rows: list[dict[str, Any]],
    *,
    failed_indexes: list[int] | None = None,
    min_rows: int = 10,
    today: str | None = None,
) -> list[dict[str, Any]]:
    """
    Build template-friendly row dicts, keeping typed values after a failed save.

    If failed_indexes is provided, only those rows (plus padding) are returned so
    successfully saved rows are not shown again.
    """
    today = today or date.today().isoformat()
    failed_set = set(failed_indexes or [])
    keep_all = failed_indexes is None

    display: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        if not keep_all and idx not in failed_set:
            continue
        if keep_all and row_is_blank(row):
            # Still keep blank submitted slots so the grid layout matches.
            pass
        display.append(
            {
                "lot_number": str(row.get("Lot Number / Palli Number") or ""),
                "receipt_date": str(row.get("Date") or today),
                "vendor_name": str(row.get("Party") or ""),
                "cloth_pv": str(row.get("PV blend") or ""),
                "cloth_read_pick": str(row.get("Read Pick") or ""),
                "rolls": "" if str(row.get("Party Thaan") or "").strip() in {"", "0"} else str(row.get("Party Thaan")),
                "factory_rolls": (
                    ""
                    if str(row.get("Factory Thaan") or "").strip() in {"", "0"}
                    else str(row.get("Factory Thaan"))
                ),
                "vendor_metres": str(row.get("Vendor Metres") or ""),
                "factory_metres": str(row.get("Factory Metres") or ""),
                "vendor_weight": (
                    ""
                    if str(row.get("Vendor Weight") or "").strip() in {"", "0"}
                    else str(row.get("Vendor Weight"))
                ),
                "factory_weight": (
                    ""
                    if str(row.get("Factory Weight") or "").strip() in {"", "0"}
                    else str(row.get("Factory Weight"))
                ),
                "remarks": str(row.get("Remarks") or ""),
                "is_invalid": idx in failed_set,
                "photo_keep": str(row.get("_image_token") or ""),
                "photo_preview_url": temp_image_url(str(row.get("_image_token") or "")),
                "needs_photo_reselect": False,
            }
        )

    empty = {
        "lot_number": "",
        "receipt_date": today,
        "vendor_name": "",
        "cloth_pv": "",
        "cloth_read_pick": "",
        "rolls": "",
        "factory_rolls": "",
        "vendor_metres": "",
        "factory_metres": "",
        "vendor_weight": "",
        "factory_weight": "",
        "remarks": "",
        "is_invalid": False,
        "photo_keep": "",
        "photo_preview_url": "",
        "needs_photo_reselect": False,
    }
    while len(display) < min_rows:
        display.append(dict(empty))
    return display


def _getlist_at(post_data, key: str, i: int) -> str:
    values = post_data.getlist(key)
    return values[i] if i < len(values) else ""


def _uploaded_file_for_row(files, i: int):
    """
    Resolve the photo for sheet row i.

    File inputs are named receipt_image_0, receipt_image_1, … so each photo
    stays with its row even when other rows have no file.
    """
    if not files:
        return None
    candidate = files.get(f"receipt_image_{i}")
    if candidate is None:
        return None
    # Browsers may submit empty file parts — treat those as no upload.
    name = getattr(candidate, "name", "") or ""
    size = getattr(candidate, "size", None)
    if not name or size == 0:
        return None
    return candidate


def parse_grid_post(post_data, files=None) -> list[dict[str, Any]]:
    """Parse repeated POST arrays from the receiving sheet form."""
    files = files or {}
    lots = post_data.getlist("lot_number")
    rows = []
    for i in range(len(lots)):
        image = _uploaded_file_for_row(files, i)
        token = _getlist_at(post_data, "photo_keep", i).strip()
        if image:
            # Stash so the photo survives a failed save / browser file-input clear.
            try:
                token = persist_temp_image(image)
                image = load_temp_image(token) or image
            except Exception:  # noqa: BLE001
                token = token or ""
        elif token:
            image = load_temp_image(token)

        rows.append(
            {
                "Lot Number / Palli Number": _getlist_at(post_data, "lot_number", i),
                "Date": _getlist_at(post_data, "receipt_date", i),
                "Party": _getlist_at(post_data, "vendor_name", i),
                "PV blend": _getlist_at(post_data, "cloth_pv", i),
                "Read Pick": _getlist_at(post_data, "cloth_read_pick", i),
                "Party Thaan": _getlist_at(post_data, "rolls", i),
                "Factory Thaan": _getlist_at(post_data, "factory_rolls", i),
                "Vendor Metres": _getlist_at(post_data, "vendor_metres", i),
                "Factory Metres": _getlist_at(post_data, "factory_metres", i),
                "Vendor Weight": _getlist_at(post_data, "vendor_weight", i),
                "Factory Weight": _getlist_at(post_data, "factory_weight", i),
                "Remarks": _getlist_at(post_data, "remarks", i),
                "_image": image,
                "_image_token": token,
            }
        )
    return rows
