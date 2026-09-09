from decimal import Decimal

from django import forms
from django.db import transaction

from accounts.permissions import can_override_stock
from audit.services.numbering import generate_transaction_number
from common.forms import BootstrapFormMixin
from inventory.models import MaterialTransaction
from inventory.services.stock import create_material_transaction, validate_stock_available
from master_data.models import Material


class MaterialTransactionForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = MaterialTransaction
        fields = [
            "transaction_number", "transaction_date", "material", "transaction_type",
            "quantity_in", "quantity_out", "unit", "related_reference", "remarks",
        ]
        widgets = {"transaction_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        transaction_type = kwargs.pop("transaction_type", None)
        super().__init__(*args, **kwargs)
        self.fields["material"].queryset = Material.objects.filter(is_active=True)
        if not self.instance.pk:
            self.fields["transaction_number"].initial = generate_transaction_number()
        if transaction_type:
            self.fields["transaction_type"].initial = transaction_type
            self.fields["transaction_type"].widget = forms.HiddenInput()

    def clean(self):
        cleaned = super().clean()
        qty_out = cleaned.get("quantity_out") or Decimal("0")
        material = cleaned.get("material")
        if material and qty_out > 0:
            try:
                validate_stock_available(
                    material.id, qty_out, allow_override=can_override_stock(self.user)
                )
            except ValueError as e:
                raise forms.ValidationError(str(e))
        return cleaned

    def save(self, commit=True, user=None):
        instance = super().save(commit=False)
        if not instance.unit and instance.material:
            instance.unit = instance.material.unit
        instance.entered_by = user
        if commit:
            instance.save()
        return instance


class PurchaseForm(MaterialTransactionForm):
    def __init__(self, *args, **kwargs):
        kwargs["transaction_type"] = "Purchase"
        super().__init__(*args, **kwargs)
        self.fields["quantity_out"].widget = forms.HiddenInput()
        self.fields["quantity_out"].initial = Decimal("0")
        self.initial["quantity_out"] = Decimal("0")


class AdjustmentInForm(MaterialTransactionForm):
    def __init__(self, *args, **kwargs):
        kwargs["transaction_type"] = "Adjustment In"
        super().__init__(*args, **kwargs)
        self.fields["quantity_out"].widget = forms.HiddenInput()
        self.fields["quantity_out"].initial = Decimal("0")
        self.initial["quantity_out"] = Decimal("0")


class AdjustmentOutForm(MaterialTransactionForm):
    def __init__(self, *args, **kwargs):
        kwargs["transaction_type"] = "Adjustment Out"
        super().__init__(*args, **kwargs)
        self.fields["quantity_in"].widget = forms.HiddenInput()
        self.fields["quantity_in"].initial = Decimal("0")
        self.initial["quantity_in"] = Decimal("0")
