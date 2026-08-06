"""Gate Entry spreadsheet parse / save helpers."""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction

from common.images import compress_image_upload
from gate_entry.models import GateEntry

GATE_HEADERS = [
    "Gate No.",
    "Date",
    "Purchaser",
    "Shop Name",
    "Chemical",
    "Electrical",
    "Mechanical",
    "General",
    "Demanded By",
]

_TEMP_TOKEN_RE = re.compile(r"^[a-f0-9]{32}$")
_GATE_NUM_RE = re.compile(r"^G(\d+)$", re.IGNORECASE)


def entry_to_excel_row(entry: GateEntry) -> list[Any]:
    """Map a saved gate entry to GATE_HEADERS values for Excel export."""
    return [
        entry.gate_number or "",
        entry.entry_date.isoformat() if entry.entry_date else "",
        entry.purchaser or "",
        entry.shop_name or "",
        entry.chemical or "",
        entry.electrical or "",
        entry.mechanical or "",
        entry.general or "",
        entry.demanded_by or "",
    ]


def _temp_image_dir() -> Path:
    path = Path(settings.MEDIA_ROOT) / "gate_entry" / "tmp"
    path.mkdir(parents=True, exist_ok=True)
    return path


def persist_temp_image(uploaded_file) -> str:
    """Store an upload under media/gate_entry/tmp and return a 32-char token."""
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
    return f"{base}gate_entry/tmp/{token}.jpg"


def _uploaded_file_for_row(files, i: int):
    upload = files.get(f"gate_image_{i}") if files is not None else None
    if not upload:
        return None
    name = (getattr(upload, "name", "") or "").strip()
    if not name:
        return None
    size = getattr(upload, "size", None)
    if size == 0:
        return None
    return upload


def next_gate_sequence_start() -> int:
    """Return the next integer n so new rows can be G{n}, G{n+1}, …"""
    highest = 0
    # Include soft-deleted so recycled gate numbers are not reused
    for value in GateEntry.all_objects.values_list("gate_number", flat=True):
        match = _GATE_NUM_RE.match(str(value or "").strip())
        if match:
            highest = max(highest, int(match.group(1)))
    return highest + 1


def format_gate_number(n: int) -> str:
    return f"G{n}"


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
    raise ValueError(f"Invalid date: {value}")


def _text(value: Any) -> str:
    return str(value or "").strip()


_STOCK_SPLIT_RE = re.compile(r"\s{2,}|\n+")


def _stock_text(value: Any) -> str:
    """Normalize stock fields into newline-separated list items."""
    text = str(value or "").strip()
    if not text:
        return ""
    parts: list[str] = []
    for part in _STOCK_SPLIT_RE.split(text):
        cleaned = re.sub(r"^\d+\.\s*", "", part.strip())
        if cleaned:
            parts.append(cleaned)
    return "\n".join(parts)


def row_is_blank(row: dict[str, Any]) -> bool:
    keys = (
        "Purchaser",
        "Shop Name",
        "Chemical",
        "Electrical",
        "Mechanical",
        "General",
        "Demanded By",
    )
    return all(not _text(row.get(k)) for k in keys)


def validate_row_complete(row: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if not _text(row.get("Date")):
        missing.append("Date")
    else:
        try:
            _to_date(row.get("Date"))
        except ValueError:
            missing.append("Date (invalid)")
    if not _text(row.get("Purchaser")):
        missing.append("Purchaser")
    if not _text(row.get("Shop Name")):
        missing.append("Shop Name")
    stock_filled = any(
        _text(row.get(k)) for k in ("Chemical", "Electrical", "Mechanical", "General")
    )
    if not stock_filled:
        missing.append("Stock Description (at least one of Chemical / Electrical / Mechanical / General)")
    if not _text(row.get("Demanded By")):
        missing.append("Demanded By")
    return missing


def _allocate_gate_number(preferred: str, used: set[str]) -> str:
    preferred = _text(preferred).upper()
    if preferred and preferred not in used and not GateEntry.all_objects.filter(gate_number__iexact=preferred).exists():
        return preferred
    n = next_gate_sequence_start()
    while True:
        candidate = format_gate_number(n)
        if candidate not in used and not GateEntry.all_objects.filter(gate_number__iexact=candidate).exists():
            return candidate
        n += 1


@transaction.atomic
def save_gate_row(row: dict[str, Any], user, used_numbers: set[str]) -> GateEntry:
    problems = validate_row_complete(row)
    if problems:
        raise ValueError("Incomplete row — fill: " + ", ".join(problems))

    gate_number = _allocate_gate_number(_text(row.get("Gate No.")), used_numbers)
    used_numbers.add(gate_number)

    image = row.get("_image")
    prepared_image = compress_image_upload(image) if image else None

    entry = GateEntry(
        gate_number=gate_number,
        entry_date=_to_date(row.get("Date")),
        purchaser=_text(row.get("Purchaser")),
        shop_name=_text(row.get("Shop Name")),
        chemical=_stock_text(row.get("Chemical")),
        electrical=_stock_text(row.get("Electrical")),
        mechanical=_stock_text(row.get("Mechanical")),
        general=_stock_text(row.get("General")),
        demanded_by=_text(row.get("Demanded By")),
        created_by=user,
        updated_by=user,
    )
    entry.full_clean(exclude=["entry_image"])
    if prepared_image:
        filename = getattr(prepared_image, "name", None) or "gate.jpg"
        entry.entry_image.save(filename, prepared_image, save=False)
    entry.save()
    clear_temp_image(str(row.get("_image_token") or ""))
    return entry


def save_gate_rows(rows: list[dict[str, Any]], user) -> tuple[int, list[str], list[int]]:
    saved = 0
    errors: list[str] = []
    failed: list[int] = []
    used: set[str] = set()
    for idx, row in enumerate(rows):
        if row_is_blank(row):
            continue
        problems = validate_row_complete(row)
        if problems:
            errors.append(f"Row {idx + 1}: not saved — fill: {', '.join(problems)}")
            failed.append(idx)
            continue
        try:
            save_gate_row(row, user, used)
            saved += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Row {idx + 1}: {exc}")
            failed.append(idx)
    return saved, errors, failed


def sheet_display_rows(
    rows: list[dict[str, Any]],
    *,
    failed_indexes: list[int] | None = None,
    min_rows: int = 8,
    today: str | None = None,
    start_seq: int | None = None,
) -> list[dict[str, Any]]:
    today = today or date.today().isoformat()
    start = start_seq or next_gate_sequence_start()
    failed_set = set(failed_indexes or [])
    keep_all = failed_indexes is None

    display: list[dict[str, Any]] = []
    seq = start
    for idx, row in enumerate(rows):
        if not keep_all and idx not in failed_set:
            continue
        gate = _text(row.get("Gate No.")) or format_gate_number(seq)
        display.append(
            {
                "gate_number": gate,
                "entry_date": str(row.get("Date") or today),
                "purchaser": _text(row.get("Purchaser")),
                "shop_name": _text(row.get("Shop Name")),
                "chemical": _stock_text(row.get("Chemical")),
                "electrical": _stock_text(row.get("Electrical")),
                "mechanical": _stock_text(row.get("Mechanical")),
                "general": _stock_text(row.get("General")),
                "demanded_by": _text(row.get("Demanded By")),
                "photo_keep": str(row.get("_image_token") or ""),
                "photo_preview_url": temp_image_url(str(row.get("_image_token") or "")),
                "is_invalid": idx in failed_set,
            }
        )
        seq += 1

    while len(display) < min_rows:
        display.append(
            {
                "gate_number": format_gate_number(start + len(display)),
                "entry_date": today,
                "purchaser": "",
                "shop_name": "",
                "chemical": "",
                "electrical": "",
                "mechanical": "",
                "general": "",
                "demanded_by": "",
                "photo_keep": "",
                "photo_preview_url": "",
                "is_invalid": False,
            }
        )
    return display


def _getlist_at(post_data, key: str, i: int) -> str:
    values = post_data.getlist(key)
    return values[i] if i < len(values) else ""


def parse_grid_post(post_data, files=None) -> list[dict[str, Any]]:
    files = files or {}
    gates = post_data.getlist("gate_number")
    rows = []
    for i in range(len(gates)):
        image = _uploaded_file_for_row(files, i)
        token = _getlist_at(post_data, "photo_keep", i).strip()
        if image:
            try:
                token = persist_temp_image(image)
                image = load_temp_image(token) or image
            except Exception:
                token = token or ""
        elif token:
            image = load_temp_image(token)

        rows.append(
            {
                "Gate No.": _getlist_at(post_data, "gate_number", i),
                "Date": _getlist_at(post_data, "entry_date", i),
                "Purchaser": _getlist_at(post_data, "purchaser", i),
                "Shop Name": _getlist_at(post_data, "shop_name", i),
                "Chemical": _getlist_at(post_data, "chemical", i),
                "Electrical": _getlist_at(post_data, "electrical", i),
                "Mechanical": _getlist_at(post_data, "mechanical", i),
                "General": _getlist_at(post_data, "general", i),
                "Demanded By": _getlist_at(post_data, "demanded_by", i),
                "_image": image,
                "_image_token": token,
            }
        )
    return rows
