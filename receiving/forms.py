from django import forms
from django.db import transaction
from django.db.models import Q

from audit.services.numbering import generate_lot_number
from common.forms import BootstrapFormMixin
from master_data.models import ClothType, Vendor
from production.services.lot import create_production_lot_from_receipt
from receiving.models import ClothReceipt


class ClothReceiptForm(BootstrapFormMixin, forms.ModelForm):
    vendor_name = forms.CharField(
        label="Vendor",
        max_length=200,
        help_text="Type the vendor name. A new vendor is created automatically if it does not exist.",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Type vendor name",
                "list": "existing-vendors",
                "autocomplete": "off",
            }
        ),
    )

    class Meta:
        model = ClothReceipt
        fields = [
            "production_lot_number",
            "receipt_date",
            "vendor_challan_number",
            "cloth_type",
            "number_of_rolls",
            "vendor_metres",
            "factory_measured_metres",
            "vendor_weight",
            "factory_measured_weight",
            "rejected_metres",
            "remarks",
        ]
        widgets = {"receipt_date": forms.DateInput(attrs={"type": "date"})}
        labels = {
            "production_lot_number": "Lot Number / Palli Number",
            "receipt_date": "Receiving Date",
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.fields["cloth_type"].queryset = ClothType.objects.filter(is_active=True)
        self.fields["production_lot_number"].help_text = (
            "Unique lot / palli number for this cloth. Same number is used in all production stages."
        )
        if self.instance.pk and self.instance.vendor_id:
            self.fields["vendor_name"].initial = self.instance.vendor.name
        if not self.instance.pk:
            self.fields["production_lot_number"].initial = generate_lot_number()
        self.vendor_suggestions = list(
            Vendor.objects.filter(is_active=True).order_by("name").values_list("name", flat=True)
        )
        self.order_fields(
            [
                "production_lot_number",
                "receipt_date",
                "vendor_name",
                "vendor_challan_number",
                "cloth_type",
                "number_of_rolls",
                "vendor_metres",
                "factory_measured_metres",
                "vendor_weight",
                "factory_measured_weight",
                "rejected_metres",
                "remarks",
            ]
        )

    def clean_vendor_name(self) -> str:
        name = (self.cleaned_data.get("vendor_name") or "").strip()
        if not name:
            raise forms.ValidationError("Vendor name is required.")
        return name

    def _resolve_vendor(self, name: str) -> Vendor:
        """Find vendor by name (case-insensitive) or create a new active vendor."""
        existing = Vendor.objects.filter(Q(name__iexact=name)).first()
        if existing:
            if not existing.is_active:
                existing.is_active = True
                existing.save(update_fields=["is_active"])
            return existing
        return Vendor.objects.create(name=name, is_active=True)

    def save(self, commit=True, user=None):
        instance = super().save(commit=False)
        instance.vendor = self._resolve_vendor(self.cleaned_data["vendor_name"])
        instance.receipt_number = instance.production_lot_number
        instance.calculate_fields()
        if commit:
            with transaction.atomic():
                instance.save()
                if not hasattr(instance, "production_lot"):
                    create_production_lot_from_receipt(instance, user)
        return instance
