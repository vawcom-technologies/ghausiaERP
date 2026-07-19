from decimal import Decimal

from django import forms
from django.db import transaction

from accounts.permissions import can_override_stock, is_supervisor
from audit.services.numbering import generate_batch_number, generate_mixture_number
from common.forms import BootstrapFormMixin
from inventory.services.stock import (
    create_material_transaction,
    get_material_stock,
    reverse_material_transaction,
    validate_stock_available,
)
from master_data.models import Employee, Machine, Material
from inventory.models import MaterialTransaction
from production.models import (
    CalenderEntry,
    ComfortEntry,
    DyeingBatch,
    DyeingMaterialUsage,
    FinishedStock,
    Mixture,
    MixtureIngredient,
    ProcessMaterialUsage,
    ProductionLot,
    SingeingEntry,
    SixChamberEntry,
)
from production.services.lot import (
    complete_dyeing_stage,
    complete_finished_stock,
    update_lot_after_calender,
    update_lot_after_comfort,
    update_lot_after_singeing,
    update_lot_after_six_chamber,
)


class ProductionLotForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ProductionLot
        fields = ["status", "remarks"]


class SingeingEntryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = SingeingEntry
        fields = [
            "production_lot", "process_date", "machine", "operator",
            "input_metres", "input_weight", "output_metres", "output_weight",
            "damaged_metres", "start_time", "end_time", "supervisor_override", "remarks",
        ]
        widgets = {
            "process_date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        lot_id = kwargs.pop("lot_id", None)
        super().__init__(*args, **kwargs)
        self.fields["machine"].queryset = Machine.objects.filter(
            is_active=True, machine_type="Singeing"
        )
        self.fields["operator"].queryset = Employee.objects.filter(is_active=True)
        lots = ProductionLot.objects.filter(
            is_cancelled=False, current_stage__in=["Receiving", "Singeing"]
        ).exclude(status__in=["Completed", "Cancelled"])
        self.fields["production_lot"].queryset = lots
        if lot_id and not self.instance.pk:
            lot = ProductionLot.objects.filter(pk=lot_id).first()
            if lot:
                self.fields["production_lot"].initial = lot
                self.fields["input_metres"].initial = lot.current_metres
                self.fields["input_weight"].initial = lot.current_weight
        if not is_supervisor(self.user):
            self.fields["supervisor_override"].widget = forms.HiddenInput()

    def clean(self):
        cleaned = super().clean()
        lot = cleaned.get("production_lot")
        if lot and not self.instance.pk:
            if SingeingEntry.objects.filter(production_lot=lot, is_cancelled=False).exists():
                raise forms.ValidationError("An active singeing entry already exists for this lot.")
        return cleaned

    def save(self, commit=True, user=None):
        instance = super().save(commit=False)
        if commit:
            with transaction.atomic():
                instance.save()
                update_lot_after_singeing(instance, user)
        return instance


class DyeingBatchForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = DyeingBatch
        fields = [
            "batch_number", "production_lot", "process_date", "jet_machine", "operator",
            "input_metres", "input_weight", "output_metres", "output_weight",
            "colour", "shade", "start_datetime", "end_datetime",
            "supervisor_override", "remarks",
        ]
        widgets = {
            "process_date": forms.DateInput(attrs={"type": "date"}),
            "start_datetime": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "end_datetime": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        lot_id = kwargs.pop("lot_id", None)
        super().__init__(*args, **kwargs)
        self.fields["jet_machine"].queryset = Machine.objects.filter(
            is_active=True, machine_type="Jet Dyeing"
        )
        self.fields["operator"].queryset = Employee.objects.filter(is_active=True)
        lots = ProductionLot.objects.filter(
            is_cancelled=False, current_stage="Dyeing"
        ).exclude(status__in=["Completed", "Cancelled"])
        self.fields["production_lot"].queryset = lots
        if lot_id and not self.instance.pk:
            lot = ProductionLot.objects.filter(pk=lot_id).first()
            if lot:
                self.fields["production_lot"].initial = lot
                self.fields["input_metres"].initial = lot.current_metres
                self.fields["input_weight"].initial = lot.current_weight
                self.fields["batch_number"].initial = generate_batch_number(lot.lot_number)
        if not is_supervisor(self.user):
            self.fields["supervisor_override"].widget = forms.HiddenInput()


class DyeingMaterialUsageForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = DyeingMaterialUsage
        fields = [
            "dyeing_batch", "material", "quantity_used", "unit",
            "mixture", "usage_datetime", "remarks",
        ]
        widgets = {"usage_datetime": forms.DateTimeInput(attrs={"type": "datetime-local"})}

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        batch_id = kwargs.pop("batch_id", None)
        super().__init__(*args, **kwargs)
        self.fields["material"].queryset = Material.objects.filter(
            is_active=True, category__in=["Chemical", "Dye"]
        )
        self.fields["dyeing_batch"].queryset = DyeingBatch.objects.filter(is_cancelled=False)
        if batch_id:
            self.fields["dyeing_batch"].initial = batch_id
        self.fields["mixture"].queryset = Mixture.objects.filter(is_cancelled=False)

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
        old_tx = None
        if not is_new:
            old_tx = MaterialTransaction.objects.filter(
                dyeing_material_usage=instance, is_cancelled=False
            ).first()
        if commit:
            with transaction.atomic():
                instance.save()
                if old_tx:
                    reverse_material_transaction(old_tx, user, "Edit correction")
                    old_tx.cancel(user, "Replaced by edit")
                tx = create_material_transaction(
                    material=instance.material,
                    transaction_type="Dyeing Usage",
                    quantity_out=instance.quantity_used,
                    unit=instance.unit,
                    user=user,
                    dyeing_batch=instance.dyeing_batch,
                    related_reference=f"Dyeing batch {instance.dyeing_batch.batch_number}",
                    remarks=instance.remarks,
                )
                tx.dyeing_material_usage = instance
                tx.save(update_fields=["dyeing_material_usage"])
        return instance


class MixtureForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Mixture
        fields = [
            "mixture_number", "dyeing_batch", "name", "preparation_datetime",
            "prepared_by", "total_quantity", "unit", "remarks",
        ]
        widgets = {"preparation_datetime": forms.DateTimeInput(attrs={"type": "datetime-local"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields["mixture_number"].initial = generate_mixture_number()
        self.fields["prepared_by"].queryset = Employee.objects.filter(is_active=True)
        self.fields["dyeing_batch"].queryset = DyeingBatch.objects.filter(is_cancelled=False)
        batch_id = self.data.get("dyeing_batch") or self.initial.get("dyeing_batch")
        if batch_id:
            self.fields["dyeing_batch"].initial = batch_id


class MixtureIngredientForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = MixtureIngredient
        fields = ["mixture", "material", "quantity", "unit", "remarks"]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        mixture_id = kwargs.pop("mixture_id", None)
        super().__init__(*args, **kwargs)
        self.fields["material"].queryset = Material.objects.filter(
            is_active=True, category__in=["Chemical", "Dye"]
        )
        self.fields["mixture"].queryset = Mixture.objects.filter(is_cancelled=False)
        if mixture_id:
            self.fields["mixture"].initial = mixture_id

    def clean_quantity(self):
        qty = self.cleaned_data["quantity"]
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
        if commit:
            with transaction.atomic():
                instance.save()
                create_material_transaction(
                    material=instance.material,
                    transaction_type="Mixture Usage",
                    quantity_out=instance.quantity,
                    unit=instance.unit,
                    user=user,
                    mixture=instance.mixture,
                    related_reference=f"Mixture {instance.mixture.mixture_number}",
                    remarks=instance.remarks,
                )
        return instance


class SixChamberEntryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = SixChamberEntry
        fields = [
            "production_lot", "process_date", "machine", "operator",
            "input_metres", "input_weight", "output_metres", "output_weight",
            "temperature", "machine_speed", "start_time", "end_time",
            "supervisor_override", "remarks",
        ]
        widgets = {
            "process_date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        lot_id = kwargs.pop("lot_id", None)
        super().__init__(*args, **kwargs)
        self.fields["machine"].queryset = Machine.objects.filter(
            is_active=True, machine_type="Six Chamber"
        )
        self.fields["operator"].queryset = Employee.objects.filter(is_active=True)
        lots = ProductionLot.objects.filter(
            is_cancelled=False, current_stage="Six Chamber", dyeing_completed=True
        ).exclude(status__in=["Completed", "Cancelled"])
        self.fields["production_lot"].queryset = lots
        if lot_id and not self.instance.pk:
            lot = ProductionLot.objects.filter(pk=lot_id).first()
            if lot:
                self.fields["production_lot"].initial = lot
                self.fields["input_metres"].initial = lot.current_metres
                self.fields["input_weight"].initial = lot.current_weight
        if not is_supervisor(self.user):
            self.fields["supervisor_override"].widget = forms.HiddenInput()

    def save(self, commit=True, user=None):
        instance = super().save(commit=False)
        if commit:
            with transaction.atomic():
                instance.save()
                update_lot_after_six_chamber(instance, user)
        return instance


class CalenderEntryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = CalenderEntry
        fields = [
            "production_lot", "process_date", "machine", "operator",
            "input_metres", "input_weight", "output_metres", "output_weight",
            "width_before", "width_after", "start_time", "end_time",
            "supervisor_override", "remarks",
        ]
        widgets = {
            "process_date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        lot_id = kwargs.pop("lot_id", None)
        super().__init__(*args, **kwargs)
        self.fields["machine"].queryset = Machine.objects.filter(
            is_active=True, machine_type="Calender"
        )
        self.fields["operator"].queryset = Employee.objects.filter(is_active=True)
        lots = ProductionLot.objects.filter(
            is_cancelled=False, current_stage="Calender"
        ).exclude(status__in=["Completed", "Cancelled"])
        self.fields["production_lot"].queryset = lots
        if lot_id and not self.instance.pk:
            lot = ProductionLot.objects.filter(pk=lot_id).first()
            if lot:
                self.fields["production_lot"].initial = lot
                self.fields["input_metres"].initial = lot.current_metres
                self.fields["input_weight"].initial = lot.current_weight
        if not is_supervisor(self.user):
            self.fields["supervisor_override"].widget = forms.HiddenInput()

    def save(self, commit=True, user=None):
        instance = super().save(commit=False)
        if commit:
            with transaction.atomic():
                instance.save()
                update_lot_after_calender(instance, user)
        return instance


class ComfortEntryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ComfortEntry
        fields = [
            "production_lot", "process_date", "machine", "operator",
            "input_metres", "input_weight", "output_metres", "output_weight",
            "width_before", "width_after", "start_time", "end_time",
            "supervisor_override", "remarks",
        ]
        widgets = {
            "process_date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        lot_id = kwargs.pop("lot_id", None)
        super().__init__(*args, **kwargs)
        self.fields["machine"].queryset = Machine.objects.filter(
            is_active=True, machine_type="Comfort"
        )
        self.fields["operator"].queryset = Employee.objects.filter(is_active=True)
        lots = ProductionLot.objects.filter(
            is_cancelled=False, current_stage="Comfort"
        ).exclude(status__in=["Completed", "Cancelled"])
        self.fields["production_lot"].queryset = lots
        if lot_id and not self.instance.pk:
            lot = ProductionLot.objects.filter(pk=lot_id).first()
            if lot:
                self.fields["production_lot"].initial = lot
                self.fields["input_metres"].initial = lot.current_metres
                self.fields["input_weight"].initial = lot.current_weight
        if not is_supervisor(self.user):
            self.fields["supervisor_override"].widget = forms.HiddenInput()

    def save(self, commit=True, user=None):
        instance = super().save(commit=False)
        if commit:
            with transaction.atomic():
                instance.save()
                update_lot_after_comfort(instance, user)
        return instance


class FinishedStockForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = FinishedStock
        fields = [
            "production_lot", "completion_date", "final_metres", "final_weight",
            "number_of_rolls", "quality_grade", "accepted_metres", "rejected_metres",
            "storage_location", "checked_by", "remarks",
        ]
        widgets = {"completion_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        lot_id = kwargs.pop("lot_id", None)
        super().__init__(*args, **kwargs)
        self.fields["checked_by"].queryset = Employee.objects.filter(is_active=True)
        lots = ProductionLot.objects.filter(
            is_cancelled=False, current_stage="Finished", status="In Production"
        ) | ProductionLot.objects.filter(is_cancelled=False, current_stage="Comfort")
        self.fields["production_lot"].queryset = lots.distinct()
        if lot_id and not self.instance.pk:
            lot = ProductionLot.objects.filter(pk=lot_id).first()
            if lot:
                self.fields["production_lot"].initial = lot
                self.fields["final_metres"].initial = lot.current_metres
                self.fields["final_weight"].initial = lot.current_weight

    def save(self, commit=True, user=None):
        instance = super().save(commit=False)
        if commit:
            with transaction.atomic():
                instance.save()
                complete_finished_stock(instance, user)
        return instance
