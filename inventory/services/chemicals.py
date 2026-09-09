"""Chemicals issue-slip spreadsheet helpers."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from django.db import transaction

from inventory.models import ChemicalIssueSlip, ChemicalStock

ISSUE_SLIP_HEADERS = [
    "Date",
    "Issue Slip Number",
    "Name",
    "Department",
    "Weight (kgs)",
    "LOT NO.",
    "Jet No.",
    "Jigar No.",
    "Total Issued",
]


def issue_slip_to_excel_row(entry: ChemicalIssueSlip) -> list[Any]:
    return [
        entry.issue_date or "",
        entry.issue_slip_number or "",
        entry.name or "",
        entry.department or "",
        entry.weight_kgs or "",
        entry.lot_number or "",
        entry.jet_number or "",
        entry.jigar_number or "",
        entry.total_issued or "",
    ]

# Letters, digits, spaces, and common factory separators
_ALPHANUM_RE = re.compile(r"^[A-Za-z0-9\s./\-]*$")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _alphanumeric(value: Any, label: str) -> str:
    text = _text(value)
    if text and not _ALPHANUM_RE.match(text):
        raise ValueError(f"{label} must be alphanumeric (letters, numbers, spaces, / . -).")
    return text


def row_is_blank(row: dict[str, Any]) -> bool:
    return all(not _text(row.get(h)) for h in ISSUE_SLIP_HEADERS)


def validate_row_complete(row: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    required = ("Date", "Issue Slip Number", "Name", "Department")
    for key in required:
        if not _text(row.get(key)):
            missing.append(key)

    # Date comes from <input type="date"> as YYYY-MM-DD — skip alphanumeric check.
    date_val = _text(row.get("Date"))
    if date_val:
        try:
            date.fromisoformat(date_val)
        except ValueError:
            missing.append("Date (invalid)")

    for key in ISSUE_SLIP_HEADERS:
        if key == "Date":
            continue
        try:
            _alphanumeric(row.get(key), key)
        except ValueError as exc:
            missing.append(str(exc))
    return missing


@transaction.atomic
def save_issue_slip_row(row: dict[str, Any], user) -> ChemicalIssueSlip:
    problems = validate_row_complete(row)
    if problems:
        raise ValueError("Incomplete / invalid row — " + "; ".join(problems))

    entry = ChemicalIssueSlip(
        issue_date=_text(row.get("Date")),
        issue_slip_number=_alphanumeric(row.get("Issue Slip Number"), "Issue Slip Number"),
        name=_alphanumeric(row.get("Name"), "Name"),
        department=_alphanumeric(row.get("Department"), "Department"),
        weight_kgs=_alphanumeric(row.get("Weight (kgs)"), "Weight (kgs)"),
        lot_number=_alphanumeric(row.get("LOT NO."), "LOT NO."),
        jet_number=_alphanumeric(row.get("Jet No."), "Jet No."),
        jigar_number=_alphanumeric(row.get("Jigar No."), "Jigar No."),
        total_issued=_alphanumeric(row.get("Total Issued"), "Total Issued"),
        created_by=user,
        updated_by=user,
    )
    entry.full_clean()
    entry.save()
    return entry


def save_issue_slip_rows(rows: list[dict[str, Any]], user) -> tuple[int, list[str], list[int]]:
    saved = 0
    errors: list[str] = []
    failed: list[int] = []
    for idx, row in enumerate(rows):
        if row_is_blank(row):
            continue
        problems = validate_row_complete(row)
        if problems:
            errors.append(f"Row {idx + 1}: not saved — {'; '.join(problems)}")
            failed.append(idx)
            continue
        try:
            save_issue_slip_row(row, user)
            saved += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Row {idx + 1}: {exc}")
            failed.append(idx)
    return saved, errors, failed


def sheet_display_rows(
    rows: list[dict[str, Any]],
    *,
    failed_indexes: list[int] | None = None,
    min_rows: int = 10,
    today: str | None = None,
) -> list[dict[str, Any]]:
    today = today or date.today().isoformat()
    failed_set = set(failed_indexes or [])
    keep_all = failed_indexes is None

    display: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        if not keep_all and idx not in failed_set:
            continue
        display.append(
            {
                "issue_date": _text(row.get("Date")) or today,
                "issue_slip_number": _text(row.get("Issue Slip Number")),
                "name": _text(row.get("Name")),
                "department": _text(row.get("Department")),
                "weight_kgs": _text(row.get("Weight (kgs)")),
                "lot_number": _text(row.get("LOT NO.")),
                "jet_number": _text(row.get("Jet No.")),
                "jigar_number": _text(row.get("Jigar No.")),
                "total_issued": _text(row.get("Total Issued")),
                "is_invalid": idx in failed_set,
            }
        )

    while len(display) < min_rows:
        display.append(
            {
                "issue_date": today,
                "issue_slip_number": "",
                "name": "",
                "department": "",
                "weight_kgs": "",
                "lot_number": "",
                "jet_number": "",
                "jigar_number": "",
                "total_issued": "",
                "is_invalid": False,
            }
        )
    return display


def _getlist_at(post_data, key: str, i: int) -> str:
    values = post_data.getlist(key)
    return values[i] if i < len(values) else ""


def parse_issue_slip_grid_post(post_data) -> list[dict[str, Any]]:
    dates = post_data.getlist("issue_date")
    rows = []
    for i in range(len(dates)):
        rows.append(
            {
                "Date": _getlist_at(post_data, "issue_date", i),
                "Issue Slip Number": _getlist_at(post_data, "issue_slip_number", i),
                "Name": _getlist_at(post_data, "name", i),
                "Department": _getlist_at(post_data, "department", i),
                "Weight (kgs)": _getlist_at(post_data, "weight_kgs", i),
                "LOT NO.": _getlist_at(post_data, "lot_number", i),
                "Jet No.": _getlist_at(post_data, "jet_number", i),
                "Jigar No.": _getlist_at(post_data, "jigar_number", i),
                "Total Issued": _getlist_at(post_data, "total_issued", i),
            }
        )
    return rows


STOCK_HEADERS = [
    "Date",
    "Name",
    "Closing Stock",
    "New Stock",
    "Total Stock",
    "Issued Stock",
    "Remaining Stock",
]


def stock_to_excel_row(entry: ChemicalStock) -> list[Any]:
    return [
        entry.stock_date or "",
        entry.name or "",
        entry.closing_stock or "",
        entry.new_stock or "",
        entry.total_stock or "",
        entry.issued_stock or "",
        entry.remaining_stock or "",
    ]


def _parse_qty(value: Any) -> float:
    text = _text(value).replace(",", "")
    text = re.sub(r"\s*kgs?\s*$", "", text, flags=re.IGNORECASE).strip()
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def _format_qty(n: float) -> str:
    if abs(n) < 1e-12:
        qty = "0"
    elif abs(n - round(n)) < 1e-9:
        qty = str(int(round(n)))
    else:
        qty = str(round(n, 3))
    return f"{qty} kgs"


def compute_stock_totals(closing: Any, new: Any, issued: Any) -> tuple[str, str]:
    closing_n = _parse_qty(closing)
    new_n = _parse_qty(new)
    issued_n = _parse_qty(issued)
    total = closing_n + new_n
    remaining = total - issued_n
    return _format_qty(total), _format_qty(remaining)


def stock_row_is_blank(row: dict[str, Any]) -> bool:
    keys = ("Date", "Name", "Closing Stock", "New Stock", "Issued Stock")
    return all(not _text(row.get(k)) for k in keys)


def validate_stock_row(row: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if not _text(row.get("Date")):
        missing.append("Date")
    else:
        try:
            date.fromisoformat(_text(row.get("Date")))
        except ValueError:
            missing.append("Date (invalid)")
    if not _text(row.get("Name")):
        missing.append("Name")
    else:
        try:
            _alphanumeric(row.get("Name"), "Name")
        except ValueError as exc:
            missing.append(str(exc))

    for key in ("Closing Stock", "New Stock", "Issued Stock"):
        val = _text(row.get(key))
        if val:
            cleaned = re.sub(r"\s*kgs?\s*$", "", val.replace(",", ""), flags=re.IGNORECASE).strip()
            try:
                float(cleaned)
            except ValueError:
                missing.append(f"{key} must be a number")
    return missing


@transaction.atomic
def save_stock_row(row: dict[str, Any], user) -> ChemicalStock:
    problems = validate_stock_row(row)
    if problems:
        raise ValueError("Incomplete / invalid row — " + "; ".join(problems))

    total, remaining = compute_stock_totals(
        row.get("Closing Stock"),
        row.get("New Stock"),
        row.get("Issued Stock"),
    )
    entry = ChemicalStock(
        stock_date=_text(row.get("Date")),
        name=_alphanumeric(row.get("Name"), "Name"),
        closing_stock=_text(row.get("Closing Stock")) or "0",
        new_stock=_text(row.get("New Stock")) or "0",
        total_stock=total,
        issued_stock=_text(row.get("Issued Stock")) or "0",
        remaining_stock=remaining,
        created_by=user,
        updated_by=user,
    )
    entry.full_clean()
    entry.save()
    return entry


def save_stock_rows(rows: list[dict[str, Any]], user) -> tuple[int, list[str], list[int]]:
    saved = 0
    errors: list[str] = []
    failed: list[int] = []
    for idx, row in enumerate(rows):
        if stock_row_is_blank(row):
            continue
        problems = validate_stock_row(row)
        if problems:
            errors.append(f"Row {idx + 1}: not saved — {'; '.join(problems)}")
            failed.append(idx)
            continue
        try:
            save_stock_row(row, user)
            saved += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Row {idx + 1}: {exc}")
            failed.append(idx)
    return saved, errors, failed


def stock_sheet_display_rows(
    rows: list[dict[str, Any]],
    *,
    failed_indexes: list[int] | None = None,
    min_rows: int = 10,
    today: str | None = None,
) -> list[dict[str, Any]]:
    today = today or date.today().isoformat()
    failed_set = set(failed_indexes or [])
    keep_all = failed_indexes is None
    display: list[dict[str, Any]] = []

    for idx, row in enumerate(rows):
        if not keep_all and idx not in failed_set:
            continue
        closing = _text(row.get("Closing Stock"))
        new = _text(row.get("New Stock"))
        issued = _text(row.get("Issued Stock"))
        total, remaining = compute_stock_totals(closing, new, issued)
        display.append(
            {
                "stock_date": _text(row.get("Date")) or today,
                "name": _text(row.get("Name")),
                "closing_stock": closing,
                "new_stock": new,
                "total_stock": total,
                "issued_stock": issued,
                "remaining_stock": remaining,
                "is_invalid": idx in failed_set,
            }
        )

    while len(display) < min_rows:
        display.append(
            {
                "stock_date": today,
                "name": "",
                "closing_stock": "",
                "new_stock": "",
                "total_stock": "",
                "issued_stock": "",
                "remaining_stock": "",
                "is_invalid": False,
            }
        )
    return display


def parse_stock_grid_post(post_data) -> list[dict[str, Any]]:
    dates = post_data.getlist("stock_date")
    rows = []
    for i in range(len(dates)):
        rows.append(
            {
                "Date": _getlist_at(post_data, "stock_date", i),
                "Name": _getlist_at(post_data, "name", i),
                "Closing Stock": _getlist_at(post_data, "closing_stock", i),
                "New Stock": _getlist_at(post_data, "new_stock", i),
                "Total Stock": _getlist_at(post_data, "total_stock", i),
                "Issued Stock": _getlist_at(post_data, "issued_stock", i),
                "Remaining Stock": _getlist_at(post_data, "remaining_stock", i),
            }
        )
    return rows
