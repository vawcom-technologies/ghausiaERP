from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from master_data.models import ClothType, Employee, Machine, Material, Vendor
from receiving.models import ClothReceipt
from production.models import (
    CalenderEntry, ComfortEntry, DyeingBatch, DyeingMaterialUsage,
    FinishedStock, Mixture, MixtureIngredient, ProcessMaterialUsage,
    ProductionLot, SingeingEntry, SixChamberEntry,
)
from gate_entry.models import GateEntry
from inventory.models import ChemicalIssueSlip, ChemicalStock, MaterialTransaction
from maintenance.models import MaintenanceJob, MaintenanceMaterialUsage
from electricity.models import DailyElectricityReading, DailyPowerReading, ElectricityMeter


class AuditAdminMixin:
    readonly_fields = (
        "created_at", "created_by", "updated_at", "updated_by",
        "cancelled_at", "cancelled_by", "cancellation_reason",
    )

    def has_delete_permission(self, request, obj=None):
        if obj and hasattr(obj, "is_cancelled"):
            return request.user.is_superuser
        return super().has_delete_permission(request, obj)


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ("name", "contact_person", "phone", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "phone")


@admin.register(ClothType)
class ClothTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "default_unit", "is_active")
    search_fields = ("name", "code")


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("name", "employee_code", "department", "role", "is_active")
    search_fields = ("name", "employee_code")


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "machine_type", "status", "is_active")
    list_filter = ("machine_type", "status", "is_active")
    search_fields = ("name", "code")


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "category", "unit", "minimum_stock", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("name", "code")


@admin.register(ClothReceipt)
class ClothReceiptAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("production_lot_number", "receipt_date", "vendor", "accepted_metres", "is_cancelled")
    list_filter = ("is_cancelled", "receipt_date")
    search_fields = ("production_lot_number", "receipt_number", "vendor_challan_number")
    date_hierarchy = "receipt_date"
    readonly_fields = AuditAdminMixin.readonly_fields + (
        "receipt_number",
        "metre_difference",
        "weight_difference",
        "accepted_metres",
    )


@admin.register(ProductionLot)
class ProductionLotAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("lot_number", "vendor", "cloth_type", "current_stage", "status", "current_metres")
    list_filter = ("current_stage", "status", "is_cancelled")
    search_fields = ("lot_number",)


@admin.register(SingeingEntry)
class SingeingEntryAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("production_lot", "process_date", "input_metres", "output_metres", "is_cancelled")
    list_filter = ("is_cancelled",)


@admin.register(DyeingBatch)
class DyeingBatchAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("batch_number", "production_lot", "colour", "output_metres", "is_cancelled")
    search_fields = ("batch_number",)


@admin.register(DyeingMaterialUsage)
class DyeingMaterialUsageAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("dyeing_batch", "material", "quantity_used", "is_cancelled")


@admin.register(Mixture)
class MixtureAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("mixture_number", "name", "dyeing_batch", "is_cancelled")


@admin.register(MixtureIngredient)
class MixtureIngredientAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("mixture", "material", "quantity")


@admin.register(SixChamberEntry)
class SixChamberEntryAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("production_lot", "process_date", "output_metres")


@admin.register(CalenderEntry)
class CalenderEntryAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("production_lot", "process_date", "output_metres")


@admin.register(ComfortEntry)
class ComfortEntryAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("production_lot", "process_date", "output_metres")


@admin.register(FinishedStock)
class FinishedStockAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("production_lot", "completion_date", "final_metres", "quality_grade")


@admin.register(ProcessMaterialUsage)
class ProcessMaterialUsageAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("production_lot", "stage", "material", "quantity_used")


@admin.register(GateEntry)
class GateEntryAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("gate_number", "entry_date", "purchaser", "shop_name", "is_cancelled")
    list_filter = ("is_cancelled", "entry_date")
    search_fields = ("gate_number", "purchaser", "shop_name")
    date_hierarchy = "entry_date"


@admin.register(ChemicalIssueSlip)
class ChemicalIssueSlipAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("issue_slip_number", "issue_date", "name", "department", "is_cancelled")
    list_filter = ("is_cancelled",)
    search_fields = ("issue_slip_number", "name", "lot_number")


@admin.register(ChemicalStock)
class ChemicalStockAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("name", "stock_date", "remaining_stock", "is_cancelled")
    list_filter = ("is_cancelled",)
    search_fields = ("name",)


@admin.register(MaterialTransaction)
class MaterialTransactionAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("transaction_number", "transaction_date", "material", "transaction_type", "quantity_in", "quantity_out")
    list_filter = ("transaction_type", "is_cancelled")
    search_fields = ("transaction_number",)
    date_hierarchy = "transaction_date"


@admin.register(MaintenanceJob)
class MaintenanceJobAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("job_number", "machine", "maintenance_type", "status", "reported_datetime")
    list_filter = ("maintenance_type", "status", "is_cancelled")
    search_fields = ("job_number", "fault_description")


@admin.register(MaintenanceMaterialUsage)
class MaintenanceMaterialUsageAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("maintenance_job", "material", "quantity_used")


@admin.register(ElectricityMeter)
class ElectricityMeterAdmin(admin.ModelAdmin):
    list_display = ("name", "meter_number", "department", "multiplier", "is_active")


@admin.register(DailyElectricityReading)
class DailyElectricityReadingAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ("reading_date", "meter", "opening_reading", "closing_reading", "units_consumed")
    list_filter = ("is_cancelled",)
    date_hierarchy = "reading_date"
    readonly_fields = AuditAdminMixin.readonly_fields + ("units_consumed",)


@admin.register(DailyPowerReading)
class DailyPowerReadingAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = (
        "record_date",
        "source_mode",
        "wapda_peak_kwh",
        "wapda_offpeak_kwh",
        "solar_kwh",
        "total_kwh",
        "peak_hours",
        "offpeak_hours",
    )
    list_filter = ("source_mode", "is_cancelled")
    date_hierarchy = "record_date"
    readonly_fields = AuditAdminMixin.readonly_fields + ("wapda_total_kwh", "total_kwh", "total_hours")
