"""Attendance register rows persisted per department / section."""

from django.db import models

from audit.models import AuditModel


class AttendanceRow(AuditModel):
    """One employee line on a department/section attendance register."""

    department_slug = models.CharField(max_length=50, db_index=True)
    section_slug = models.CharField(max_length=50, blank=True, default="", db_index=True)
    row_number = models.PositiveSmallIntegerField(default=1)
    name = models.CharField(max_length=200, blank=True, default="")
    father_name = models.CharField(max_length=200, blank=True, default="")
    total_overtime_hours = models.CharField(max_length=50, blank=True, default="")
    work_status = models.CharField(max_length=100, blank=True, default="")
    decided_salary = models.CharField(max_length=50, blank=True, default="")
    total_hours = models.CharField(max_length=50, blank=True, default="")
    # {"1": {"pa": "P", "check_in": "08:00", "check_out": "17:00", "hours_worked": "9"}, ...}
    days_data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["row_number", "id"]
        verbose_name = "Attendance Row"
        verbose_name_plural = "Attendance Rows"
        indexes = [
            models.Index(fields=["department_slug", "section_slug"]),
        ]

    def __str__(self) -> str:
        label = self.name or f"Row {self.row_number}"
        scope = self.section_slug or self.department_slug
        return f"{scope}: {label}"
