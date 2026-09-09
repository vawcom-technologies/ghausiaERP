from django.contrib import admin

from attendance.models import AttendanceRow


@admin.register(AttendanceRow)
class AttendanceRowAdmin(admin.ModelAdmin):
    list_display = (
        "department_slug",
        "section_slug",
        "row_number",
        "name",
        "father_name",
        "total_hours",
        "updated_at",
    )
    list_filter = ("department_slug", "section_slug")
    search_fields = ("name", "father_name", "work_status")
