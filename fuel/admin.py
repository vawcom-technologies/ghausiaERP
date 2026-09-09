from django.contrib import admin

from fuel.models import OilBoilerShiftRecord, SteamBoilerShiftRecord


@admin.register(SteamBoilerShiftRecord)
class SteamBoilerShiftRecordAdmin(admin.ModelAdmin):
    list_display = (
        "record_date",
        "shift",
        "kuttal_quantity",
        "kuttal_price",
        "kuttal_daily_price",
        "lunda_quantity",
        "lunda_price",
        "lunda_daily_price",
        "total_daily_price",
        "updated_at",
    )
    list_filter = ("shift", "record_date")
    search_fields = ("remarks",)
    date_hierarchy = "record_date"


@admin.register(OilBoilerShiftRecord)
class OilBoilerShiftRecordAdmin(admin.ModelAdmin):
    list_display = (
        "record_date",
        "shift",
        "run_hours",
        "kuttal_quantity",
        "kuttal_daily_price",
        "lunda_quantity",
        "lunda_daily_price",
        "fuel_quantity",
        "fuel_daily_price",
        "total_daily_price",
        "updated_at",
    )
    list_filter = ("shift", "record_date")
    search_fields = ("remarks",)
    date_hierarchy = "record_date"
