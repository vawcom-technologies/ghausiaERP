"""Gate Entry spreadsheet parse / save helpers."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from django.db import transaction

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

_GATE_NUM_RE = re.compile(r"^G(\d+)$", re.IGNORECASE)


def next_gate_sequence_start() -> int:
    """Return the next integer n so new rows can be G{n}, G{n+1}, …"""
    highest = 0
    for value in GateEntry.objects.values_list("gate_number", flat=True):
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
    if preferred and preferred not in used and not GateEntry.objects.filter(gate_number__iexact=preferred).exists():
        return preferred
    n = next_gate_sequence_start()
    while True:
        candidate = format_gate_number(n)
        if candidate not in used and not GateEntry.objects.filter(gate_number__iexact=candidate).exists():
            return candidate
        n += 1


@transaction.atomic
def save_gate_row(row: dict[str, Any], user, used_numbers: set[str]) -> GateEntry:
    problems = validate_row_complete(row)
    if problems:
        raise ValueError("Incomplete row — fill: " + ", ".join(problems))

    gate_number = _allocate_gate_number(_text(row.get("Gate No.")), used_numbers)
    used_numbers.add(gate_number)

    entry = GateEntry(
        gate_number=gate_number,
        entry_date=_to_date(row.get("Date")),
        purchaser=_text(row.get("Purchaser")),
        shop_name=_text(row.get("Shop Name")),
        chemical=_text(row.get("Chemical")),
        electrical=_text(row.get("Electrical")),
        mechanical=_text(row.get("Mechanical")),
        general=_text(row.get("General")),
        demanded_by=_text(row.get("Demanded By")),
        created_by=user,
        updated_by=user,
    )
    entry.full_clean()
    entry.save()
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
                "chemical": _text(row.get("Chemical")),
                "electrical": _text(row.get("Electrical")),
                "mechanical": _text(row.get("Mechanical")),
                "general": _text(row.get("General")),
                "demanded_by": _text(row.get("Demanded By")),
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
                "is_invalid": False,
            }
        )
    return display


def _getlist_at(post_data, key: str, i: int) -> str:
    values = post_data.getlist(key)
    return values[i] if i < len(values) else ""


def parse_grid_post(post_data) -> list[dict[str, Any]]:
    gates = post_data.getlist("gate_number")
    rows = []
    for i in range(len(gates)):
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
            }
        )
    return rows
