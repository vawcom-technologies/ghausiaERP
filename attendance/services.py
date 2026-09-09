"""Save / load / export helpers for attendance registers."""

from __future__ import annotations

from typing import Any

from django.db import transaction

from attendance.models import AttendanceRow

DAY_COUNT = 15
DAY_FIELDS = ("pa", "check_in", "check_out", "hours_worked")

ATTENDANCE_EXPORT_HEADERS = [
    "Name",
    "Father Name",
    "Total Overtime Hours",
    "Work Status",
    "Decided Salary",
    "Total Hours",
]
for _day in range(1, DAY_COUNT + 1):
    ATTENDANCE_EXPORT_HEADERS.extend(
        [
            f"D{_day} P/A",
            f"D{_day} Check-in",
            f"D{_day} Check-out",
            f"D{_day} Hours Worked",
        ]
    )


def _text(value: Any) -> str:
    return str(value or "").strip()


def _getlist_at(post_data, key: str, i: int) -> str:
    values = post_data.getlist(key)
    return values[i] if i < len(values) else ""


def register_key(department_slug: str, section_slug: str = "") -> tuple[str, str]:
    return department_slug, section_slug or ""


def empty_days() -> dict[str, dict[str, str]]:
    return {
        str(day): {field: "" for field in DAY_FIELDS}
        for day in range(1, DAY_COUNT + 1)
    }


def row_is_blank(row: dict[str, Any]) -> bool:
    if any(
        _text(row.get(k))
        for k in ("name", "father_name", "total_overtime_hours", "work_status", "decided_salary")
    ):
        return False
    days = row.get("days") or {}
    for day_data in days.values():
        if any(_text(day_data.get(f)) for f in DAY_FIELDS):
            return False
    return True


def parse_register_post(post_data) -> list[dict[str, Any]]:
    names = post_data.getlist("name")
    rows: list[dict[str, Any]] = []
    for i in range(len(names)):
        days: dict[str, dict[str, str]] = {}
        for day in range(1, DAY_COUNT + 1):
            days[str(day)] = {
                field: _getlist_at(post_data, f"day_{day}_{field}", i)
                for field in DAY_FIELDS
            }
        rows.append(
            {
                "name": _getlist_at(post_data, "name", i),
                "father_name": _getlist_at(post_data, "father_name", i),
                "total_overtime_hours": _getlist_at(post_data, "total_overtime_hours", i),
                "work_status": _getlist_at(post_data, "work_status", i),
                "decided_salary": _getlist_at(post_data, "decided_salary", i),
                "total_hours": _getlist_at(post_data, "total_hours", i),
                "days": days,
            }
        )
    return rows


@transaction.atomic
def save_register_rows(
    department_slug: str,
    section_slug: str,
    rows: list[dict[str, Any]],
    user,
) -> tuple[int, list[AttendanceRow]]:
    """Replace the register for this dept/section with posted rows."""
    dept, section = register_key(department_slug, section_slug)
    AttendanceRow.objects.filter(department_slug=dept, section_slug=section).delete()

    saved_rows: list[AttendanceRow] = []
    row_number = 0
    for row in rows:
        if row_is_blank(row):
            continue
        row_number += 1
        days = empty_days()
        for day, data in (row.get("days") or {}).items():
            key = str(day)
            if key not in days:
                continue
            days[key] = {field: _text((data or {}).get(field)) for field in DAY_FIELDS}
        entry = AttendanceRow(
            department_slug=dept,
            section_slug=section,
            row_number=row_number,
            name=_text(row.get("name")),
            father_name=_text(row.get("father_name")),
            total_overtime_hours=_text(row.get("total_overtime_hours")),
            work_status=_text(row.get("work_status")),
            decided_salary=_text(row.get("decided_salary")),
            total_hours=_text(row.get("total_hours")),
            days_data=days,
            created_by=user,
            updated_by=user,
        )
        entry.save()
        saved_rows.append(entry)
    return len(saved_rows), saved_rows


def load_register_rows(department_slug: str, section_slug: str = "") -> list[AttendanceRow]:
    dept, section = register_key(department_slug, section_slug)
    return list(
        AttendanceRow.objects.filter(department_slug=dept, section_slug=section).order_by(
            "row_number", "id"
        )
    )


def _days_as_list(days: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    """Template-friendly day payload: [{day, pa, check_in, ...}, ...]."""
    result = []
    for day in range(1, DAY_COUNT + 1):
        data = days.get(str(day)) or {}
        result.append(
            {
                "day": day,
                "pa": _text(data.get("pa")),
                "check_in": _text(data.get("check_in")),
                "check_out": _text(data.get("check_out")),
                "hours_worked": _text(data.get("hours_worked")),
            }
        )
    return result


def sheet_display_rows(
    saved: list[AttendanceRow],
    *,
    min_rows: int = 15,
) -> list[dict[str, Any]]:
    display: list[dict[str, Any]] = []
    for obj in saved:
        days = empty_days()
        raw = obj.days_data or {}
        for day, data in raw.items():
            key = str(day)
            if key in days:
                days[key] = {field: _text((data or {}).get(field)) for field in DAY_FIELDS}
        display.append(
            {
                "pk": obj.pk,
                "name": obj.name,
                "father_name": obj.father_name,
                "total_overtime_hours": obj.total_overtime_hours,
                "work_status": obj.work_status,
                "decided_salary": obj.decided_salary,
                "total_hours": obj.total_hours,
                "day_list": _days_as_list(days),
            }
        )
    while len(display) < min_rows:
        display.append(
            {
                "pk": "",
                "name": "",
                "father_name": "",
                "total_overtime_hours": "",
                "work_status": "",
                "decided_salary": "",
                "total_hours": "",
                "day_list": _days_as_list(empty_days()),
            }
        )
    return display


def attendance_to_excel_row(obj: AttendanceRow) -> list[Any]:
    values: list[Any] = [
        obj.name or "",
        obj.father_name or "",
        obj.total_overtime_hours or "",
        obj.work_status or "",
        obj.decided_salary or "",
        obj.total_hours or "",
    ]
    days = obj.days_data or {}
    for day in range(1, DAY_COUNT + 1):
        data = days.get(str(day)) or {}
        values.extend(
            [
                _text(data.get("pa")),
                _text(data.get("check_in")),
                _text(data.get("check_out")),
                _text(data.get("hours_worked")),
            ]
        )
    return values
