from django import forms
from django.db import transaction

from accounts.permissions import can_override_stock
from audit.services.numbering import generate_maintenance_job_number
from common.forms import BootstrapFormMixin
from inventory.models import MaterialTransaction
from inventory.services.stock import create_material_transaction, reverse_material_transaction, validate_stock_available
from master_data.models import Employee, Machine, Material
from maintenance.models import MaintenanceJob, MaintenanceMaterialUsage
from maintenance.services.maintenance import populate_breakdown_history, update_machine_status_on_job_change


class MaintenanceJobForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = MaintenanceJob
        fields = [
            "job_number", "machine", "maintenance_type", "reported_datetime",
            "reported_by", "fault_category", "fault_description",
            "repair_started_datetime", "repair_completed_datetime",
            "machine_restarted_datetime", "technician", "repair_description",
            "root_cause", "status", "remarks",
        ]
        widgets = {
            "reported_datetime": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "repair_started_datetime": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "repair_completed_datetime": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "machine_restarted_datetime": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["machine"].queryset = Machine.objects.filter(is_active=True)
        self.fields["reported_by"].queryset = Employee.objects.filter(is_active=True)
        self.fields["technician"].queryset = Employee.objects.filter(is_active=True)
        if not self.instance.pk:
            self.fields["job_number"].initial = generate_maintenance_job_number()

    def save(self, commit=True, user=None):
        instance = super().save(commit=False)
        populate_breakdown_history(instance)
        if commit:
            with transaction.atomic():
                instance.save()
                update_machine_status_on_job_change(instance)
        return instance


class MaintenanceMaterialUsageForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = MaintenanceMaterialUsage
        fields = ["maintenance_job", "material", "quantity_used", "unit", "usage_date", "remarks"]
        widgets = {"usage_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        job_id = kwargs.pop("job_id", None)
        super().__init__(*args, **kwargs)
        self.fields["material"].queryset = Material.objects.filter(
            is_active=True, category__in=["Oil", "Grease", "Maintenance Item"]
        )
        self.fields["maintenance_job"].queryset = MaintenanceJob.objects.filter(is_cancelled=False)
        if job_id:
            self.fields["maintenance_job"].initial = job_id

    def clean_quantity_used(self):
        qty = self.cleaned_data["quantity_used"]
        material = self.cleaned_data.get("material")
        if material and qty:
            try:
                validate_stock_available(
                    material.id, qty, allow_override=can_override_stock(self.user)
                )
            except ValueError as e:
                raise forms.ValidationError(str(e))
        return qty

    def save(self, commit=True, user=None):
        instance = super().save(commit=False)
        if not instance.unit and instance.material:
            instance.unit = instance.material.unit
        is_new = instance.pk is None
        old_tx = None
        if not is_new:
            old_tx = MaterialTransaction.objects.filter(
                maintenance_material_usage=instance, is_cancelled=False
            ).first()
        if commit:
            with transaction.atomic():
                instance.save()
                if old_tx:
                    reverse_material_transaction(old_tx, user, "Edit correction")
                    old_tx.cancel(user, "Replaced by edit")
                tx = create_material_transaction(
                    material=instance.material,
                    transaction_type="Maintenance Usage",
                    quantity_out=instance.quantity_used,
                    unit=instance.unit,
                    user=user,
                    maintenance_job=instance.maintenance_job,
                    related_reference=f"Maintenance {instance.maintenance_job.job_number}",
                    remarks=instance.remarks,
                )
                tx.maintenance_material_usage = instance
                tx.save(update_fields=["maintenance_material_usage"])
        return instance
