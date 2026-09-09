from django.contrib import admin

from accounts.models import WorkAssignment


@admin.register(WorkAssignment)
class WorkAssignmentAdmin(admin.ModelAdmin):
    list_display = ("user", "module", "assigned_by", "assigned_at")
    list_filter = ("module",)
    search_fields = ("user__username",)
