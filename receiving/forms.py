from decimal import Decimal

from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.db.models import Q

from common.forms import BootstrapFormMixin
from common.images import compress_image_upload
from master_data.models import ClothType, Vendor
from production.services.lot import create_production_lot_from_receipt
from receiving.models import ClothReceipt
from receiving.services.bulk import cloth_qty_meaningful, normalize_cloth_qty, resolve_cloth_type


class ClothReceiptForm(BootstrapFormMixin, forms.ModelForm):
    vendor_name = forms.CharField(
        label="Party",
        max_length=200,
        widget=forms.TextInput(
            attrs={
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
            "pv_blend_qty",
            "read_pick_qty",
            "number_of_rolls",
            "factory_number_of_rolls",
            "vendor_metres",
            "factory_measured_metres",
            "vendor_weight",
            "factory_measured_weight",
            "remarks",
            "receipt_image",
        ]
        widgets = {
            "receipt_date": forms.DateInput(attrs={"type": "date"}),
            "remarks": forms.TextInput(),
            "receipt_image": forms.FileInput(
                attrs={"accept": "image/*", "class": "form-control"}
            ),
            "pv_blend_qty": forms.TextInput(attrs={"autocomplete": "off"}),
            "read_pick_qty": forms.TextInput(attrs={"autocomplete": "off"}),
            "number_of_rolls": forms.TextInput(attrs={"autocomplete": "off"}),
            "factory_number_of_rolls": forms.TextInput(attrs={"autocomplete": "off"}),
            "vendor_metres": forms.TextInput(attrs={"autocomplete": "off"}),
            "factory_measured_metres": forms.TextInput(attrs={"autocomplete": "off"}),
            "vendor_weight": forms.TextInput(attrs={"autocomplete": "off"}),
            "factory_measured_weight": forms.TextInput(attrs={"autocomplete": "off"}),
        }
        labels = {
            "production_lot_number": "Lot / Palli No.",
            "receipt_date": "Date",
            "pv_blend_qty": "PV blend",
            "read_pick_qty": "Read Pick",
            "number_of_rolls": "Party Thaan",
            "factory_number_of_rolls": "Factory Thaan",
            "vendor_metres": "Vendor M",
            "factory_measured_metres": "Factory M",
            "vendor_weight": "Vendor wt",
            "factory_measured_weight": "Factory wt",
            "remarks": "Remarks",
            "receipt_image": "Photo",
        }

    LABEL_URDU = {
        "production_lot_number": "لاٹ / پلی نمبر",
        "vendor_name": "پارٹی",
        "number_of_rolls": "پارٹی تھان نمبر",
        "factory_number_of_rolls": "فیکٹری تھان نمبر",
        "vendor_metres": "پارٹی غزانہ",
        "factory_measured_metres": "فیکٹری غزانہ",
        "vendor_weight": "پارٹی وزن",
        "factory_measured_weight": "فیکٹری وزن",
        "remarks": "ریمارکس",
    }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.fields["production_lot_number"].required = True
        self.fields["receipt_image"].required = False
        self.fields["remarks"].required = False
        self.fields["pv_blend_qty"].required = False
        self.fields["read_pick_qty"].required = False

        # Clear instructional help / zero placeholders on entry fields
        for name in self.fields:
            self.fields[name].help_text = ""
            self.fields[name].widget.attrs.pop("placeholder", None)

        zero_hint_fields = (
            "number_of_rolls",
            "factory_number_of_rolls",
            "vendor_weight",
            "factory_measured_weight",
        )
        self.fields["vendor_weight"].required = False
        self.fields["factory_measured_weight"].required = False
        if not self.is_bound:
            for name in zero_hint_fields:
                current = getattr(self.instance, name, None) if self.instance.pk else None
                if current in (None, "", 0, "0", Decimal("0")):
                    self.fields[name].initial = None
                    self.initial[name] = None

        # Strip required asterisk added by BootstrapFormMixin for optional cloth fields
        for name in ("pv_blend_qty", "read_pick_qty", "vendor_weight", "factory_measured_weight"):
            label = self.fields[name].label or ""
            self.fields[name].label = label.rstrip(" *").rstrip("*").strip()

        if self.instance.pk and self.instance.vendor_id:
            self.fields["vendor_name"].initial = self.instance.vendor.name

        self.vendor_suggestions = list(
            Vendor.objects.filter(is_active=True).order_by("name").values_list("name", flat=True)
        )
        self.order_fields(
            [
                "production_lot_number",
                "receipt_date",
                "vendor_name",
                "pv_blend_qty",
                "read_pick_qty",
                "number_of_rolls",
                "factory_number_of_rolls",
                "vendor_metres",
                "factory_measured_metres",
                "vendor_weight",
                "factory_measured_weight",
                "remarks",
                "receipt_image",
            ]
        )

    def clean_vendor_name(self) -> str:
        name = (self.cleaned_data.get("vendor_name") or "").strip()
        if not name:
            raise forms.ValidationError("Party name is required.")
        return name

    def clean_production_lot_number(self) -> str:
        lot = (self.cleaned_data.get("production_lot_number") or "").strip()
        if not lot:
            raise forms.ValidationError("Lot / Palli Number is required.")
        return lot

    def clean_pv_blend_qty(self) -> str:
        # Keep any typed characters; lone "/" means empty.
        return normalize_cloth_qty(self.cleaned_data.get("pv_blend_qty"))

    def clean_read_pick_qty(self) -> str:
        return normalize_cloth_qty(self.cleaned_data.get("read_pick_qty"))

    def clean_vendor_weight(self) -> str:
        return normalize_cloth_qty(self.cleaned_data.get("vendor_weight"))

    def clean_factory_measured_weight(self) -> str:
        return normalize_cloth_qty(self.cleaned_data.get("factory_measured_weight"))

    def clean(self):
        cleaned = super().clean()
        pv = cleaned.get("pv_blend_qty") or ""
        rp = cleaned.get("read_pick_qty") or ""
        if not cloth_qty_meaningful(pv) and not cloth_qty_meaningful(rp):
            raise forms.ValidationError("Enter PV blend and/or Read Pick.")

        party_thaan = cleaned.get("number_of_rolls") or 0
        factory_thaan = cleaned.get("factory_number_of_rolls") or 0
        if party_thaan <= 0:
            self.add_error("number_of_rolls", "Party Thaan must be greater than 0.")
        if factory_thaan <= 0:
            self.add_error("factory_number_of_rolls", "Factory Thaan must be greater than 0.")

        vendor_m = cleaned.get("vendor_metres")
        factory_m = cleaned.get("factory_measured_metres")
        if vendor_m is None or vendor_m <= 0:
            self.add_error("vendor_metres", "Vendor M must be greater than 0.")
        if factory_m is None or factory_m <= 0:
            self.add_error("factory_measured_metres", "Factory M must be greater than 0.")
        return cleaned

    def clean_receipt_image(self):
        image = self.cleaned_data.get("receipt_image")
        if not isinstance(image, UploadedFile):
            return image
        # Keep original when compression is not possible (e.g. some phone formats).
        return compress_image_upload(image)

    def _resolve_vendor(self, name: str) -> Vendor:
        existing = Vendor.objects.filter(Q(name__iexact=name)).first()
        if existing:
            if not existing.is_active:
                existing.is_active = True
                existing.save(update_fields=["is_active"])
            return existing
        return Vendor.objects.create(name=name, is_active=True)

    def _resolve_cloth_type(self, pv: str, rp: str) -> ClothType:
        pv_ok = cloth_qty_meaningful(pv)
        rp_ok = cloth_qty_meaningful(rp)
        if rp_ok and not pv_ok:
            name = "Read Pick"
            code = "RP"
        else:
            name = "PV blend"
            code = "PV"
        try:
            return resolve_cloth_type(name)
        except ValueError:
            ct, _ = ClothType.objects.get_or_create(
                name=name,
                defaults={"code": code, "is_active": True},
            )
            if not ct.is_active:
                ct.is_active = True
                ct.save(update_fields=["is_active"])
            return ct

    def save(self, commit=True, user=None):
        image = self.cleaned_data.get("receipt_image")
        instance = super().save(commit=False)
        instance.vendor = self._resolve_vendor(self.cleaned_data["vendor_name"])
        instance.receipt_number = instance.production_lot_number
        pv = self.cleaned_data.get("pv_blend_qty") or ""
        rp = self.cleaned_data.get("read_pick_qty") or ""
        instance.pv_blend_qty = pv
        instance.read_pick_qty = rp
        instance.cloth_type = self._resolve_cloth_type(pv, rp)
        instance.rejected_metres = Decimal("0")
        instance.calculate_fields()
        if commit:
            with transaction.atomic():
                # Persist file explicitly so photo is never dropped on create/update.
                if isinstance(image, UploadedFile):
                    filename = getattr(image, "name", None) or "receipt.jpg"
                    instance.receipt_image.save(filename, image, save=False)
                instance.save()
                if not hasattr(instance, "production_lot"):
                    create_production_lot_from_receipt(instance, user)
        return instance
