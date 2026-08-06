from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction

from common.forms import BootstrapFormMixin
from common.images import compress_image_upload
from gate_entry.models import GateEntry
from gate_entry.services import _stock_text


class GateEntryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = GateEntry
        fields = [
            "gate_number",
            "entry_date",
            "purchaser",
            "shop_name",
            "chemical",
            "electrical",
            "mechanical",
            "general",
            "demanded_by",
            "entry_image",
        ]
        widgets = {
            "entry_date": forms.DateInput(attrs={"type": "date"}),
            "gate_number": forms.TextInput(attrs={"readonly": True}),
            "chemical": forms.Textarea(attrs={"rows": 4}),
            "electrical": forms.Textarea(attrs={"rows": 4}),
            "mechanical": forms.Textarea(attrs={"rows": 4}),
            "general": forms.Textarea(attrs={"rows": 4}),
            "entry_image": forms.FileInput(attrs={"accept": "image/*"}),
        }
        labels = {
            "gate_number": "Gate No.",
            "entry_date": "Date",
            "purchaser": "Purchaser",
            "shop_name": "Shop Name",
            "chemical": "Chemical",
            "electrical": "Electrical",
            "mechanical": "Mechanical",
            "general": "General",
            "demanded_by": "Demanded By",
            "entry_image": "Photo",
        }

    LABEL_URDU = {
        "gate_number": "گیٹ نمبر",
        "entry_date": "تاریخ",
        "purchaser": "خریدار",
        "shop_name": "دکان کا نام",
        "chemical": "کیمیکل",
        "electrical": "الیکٹریکل",
        "mechanical": "مکینیکل",
        "general": "جنرل",
        "demanded_by": "مطالبہ کنندہ",
        "entry_image": "تصویر",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("chemical", "electrical", "mechanical", "general"):
            self.fields[name].widget.attrs["class"] = "form-control gate-stock-input"
            self.fields[name].widget.attrs["rows"] = 4
            self.fields[name].widget.attrs["placeholder"] = (
                "1. item — Space Space for next point"
            )
        self.fields["gate_number"].disabled = True
        self.fields["gate_number"].required = False
        self.fields["entry_image"].required = False

    def clean_gate_number(self):
        # Disabled fields are omitted from POST; keep the instance value.
        if self.instance and self.instance.pk:
            return self.instance.gate_number
        return self.cleaned_data.get("gate_number")

    def clean_chemical(self):
        return _stock_text(self.cleaned_data.get("chemical"))

    def clean_electrical(self):
        return _stock_text(self.cleaned_data.get("electrical"))

    def clean_mechanical(self):
        return _stock_text(self.cleaned_data.get("mechanical"))

    def clean_general(self):
        return _stock_text(self.cleaned_data.get("general"))

    def clean_entry_image(self):
        image = self.cleaned_data.get("entry_image")
        if not isinstance(image, UploadedFile):
            return image
        return compress_image_upload(image)

    def clean(self):
        cleaned = super().clean()
        stock = any(
            cleaned.get(f)
            for f in ("chemical", "electrical", "mechanical", "general")
        )
        if not stock:
            raise forms.ValidationError(
                "Fill at least one Stock Description column "
                "(Chemical, Electrical, Mechanical, or General)."
            )
        return cleaned

    def save(self, commit=True):
        image = self.cleaned_data.get("entry_image")
        instance = super().save(commit=False)
        if commit:
            with transaction.atomic():
                if isinstance(image, UploadedFile):
                    filename = getattr(image, "name", None) or "gate.jpg"
                    instance.entry_image.save(filename, image, save=False)
                instance.save()
        return instance
