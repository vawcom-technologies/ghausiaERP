"""Excel template and import helpers using openpyxl."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from django.http import HttpResponse
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill


def build_template_response(
    filename: str,
    headers: list[str],
    sample_rows: list[list[Any]] | None = None,
    sheet_title: str = "Data",
) -> HttpResponse:
    """Create an .xlsx download with header row and optional sample rows."""
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title

    header_fill = PatternFill("solid", fgColor="1A3A5C")
    header_font = Font(color="FFFFFF", bold=True)

    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")
        ws.column_dimensions[cell.column_letter].width = max(14, len(header) + 2)

    if sample_rows:
        for r_idx, row in enumerate(sample_rows, start=2):
            for c_idx, value in enumerate(row, start=1):
                ws.cell(row=r_idx, column=c_idx, value=value)

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def read_sheet_rows(uploaded_file, expected_headers: list[str]) -> list[dict[str, Any]]:
    """
    Read first worksheet rows keyed by header name.

    Raises ValueError if required headers are missing.
    Skips completely empty rows.
    """
    wb = load_workbook(uploaded_file, data_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    try:
        header_row = next(rows_iter)
    except StopIteration:
        raise ValueError("Excel file is empty.")

    headers = [str(h).strip() if h is not None else "" for h in header_row]
    missing = [h for h in expected_headers if h not in headers]
    if missing:
        raise ValueError(
            "Missing columns in Excel: "
            + ", ".join(missing)
            + ". Download the template and keep the header row."
        )

    index = {name: headers.index(name) for name in expected_headers}
    result: list[dict[str, Any]] = []
    for row in rows_iter:
        if row is None or all(cell is None or str(cell).strip() == "" for cell in row):
            continue
        item = {}
        for name, col in index.items():
            value = row[col] if col < len(row) else None
            if isinstance(value, str):
                value = value.strip()
            item[name] = value
        result.append(item)
    return result


def cell_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
