from decimal import Decimal, InvalidOperation

from django import forms

from common.forms import BootstrapFormMixin, blank_zero_entry_initials
from fuel.models import OilBoilerShiftRecord, SteamBoilerShiftRecord

_TEXT_ATTRS = {"class": "form-control", "autocomplete": "off"}


class SteamBoilerShiftForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = SteamBoilerShiftRecord
        fields = [
            "record_date",
            "shift",
            "kuttal_quantity",
            "kuttal_price",
            "lunda_quantity",
            "lunda_price",
            "remarks",
        ]
        widgets = {
            "record_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control", "required": True}
            ),
            "shift": forms.HiddenInput(),
            "kuttal_quantity": forms.TextInput(attrs=_TEXT_ATTRS),
            "kuttal_price": forms.TextInput(attrs=_TEXT_ATTRS),
            "lunda_quantity": forms.TextInput(attrs=_TEXT_ATTRS),
            "lunda_price": forms.TextInput(attrs=_TEXT_ATTRS),
            "remarks": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Optional remarks"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        blank_zero_entry_initials(self)

    def clean_shift(self):
        shift = self.cleaned_data.get("shift")
        if shift not in (SteamBoilerShiftRecord.SHIFT_1, SteamBoilerShiftRecord.SHIFT_2):
            raise forms.ValidationError("Select Shift 1 or Shift 2.")
        return shift

    def _clean_non_negative(self, field_name: str) -> Decimal:
        value = self.cleaned_data.get(field_name)
        if value is None:
            return Decimal("0")
        try:
            qty = Decimal(value)
        except (InvalidOperation, TypeError) as exc:
            raise forms.ValidationError("Enter a valid number.") from exc
        if qty < 0:
            raise forms.ValidationError("Value cannot be negative.")
        return qty

    def clean_kuttal_quantity(self):
        return self._clean_non_negative("kuttal_quantity")

    def clean_kuttal_price(self):
        return self._clean_non_negative("kuttal_price")

    def clean_lunda_quantity(self):
        return self._clean_non_negative("lunda_quantity")

    def clean_lunda_price(self):
        return self._clean_non_negative("lunda_price")

    def clean(self):
        cleaned = super().clean()
        record_date = cleaned.get("record_date")
        shift = cleaned.get("shift")
        if record_date and shift:
            qs = SteamBoilerShiftRecord.objects.filter(
                record_date=record_date,
                shift=shift,
                is_cancelled=False,
                is_deleted=False,
            )
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error(
                    None,
                    f"A record for {record_date} Shift {shift} already exists. "
                    "Open that date and shift to update it.",
                )
        return cleaned


class OilBoilerShiftForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = OilBoilerShiftRecord
        fields = [
            "record_date",
            "shift",
            "run_hours",
            "kuttal_quantity",
            "kuttal_price",
            "lunda_quantity",
            "lunda_price",
            "fuel_quantity",
            "fuel_price",
            "remarks",
        ]
        widgets = {
            "record_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control", "required": True}
            ),
            "shift": forms.HiddenInput(),
            "run_hours": forms.TextInput(attrs=_TEXT_ATTRS),
            "kuttal_quantity": forms.TextInput(attrs=_TEXT_ATTRS),
            "kuttal_price": forms.TextInput(attrs=_TEXT_ATTRS),
            "lunda_quantity": forms.TextInput(attrs=_TEXT_ATTRS),
            "lunda_price": forms.TextInput(attrs=_TEXT_ATTRS),
            "fuel_quantity": forms.TextInput(attrs=_TEXT_ATTRS),
            "fuel_price": forms.TextInput(attrs=_TEXT_ATTRS),
            "remarks": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Optional remarks"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        blank_zero_entry_initials(self)

    def clean_shift(self):
        shift = self.cleaned_data.get("shift")
        if shift not in (OilBoilerShiftRecord.SHIFT_1, OilBoilerShiftRecord.SHIFT_2):
            raise forms.ValidationError("Select Shift 1 or Shift 2.")
        return shift

    def _clean_non_negative(self, field_name: str) -> Decimal:
        value = self.cleaned_data.get(field_name)
        if value is None:
            return Decimal("0")
        try:
            qty = Decimal(value)
        except (InvalidOperation, TypeError) as exc:
            raise forms.ValidationError("Enter a valid number.") from exc
        if qty < 0:
            raise forms.ValidationError("Value cannot be negative.")
        return qty

    def clean_run_hours(self):
        return self._clean_non_negative("run_hours")

    def clean_kuttal_quantity(self):
        return self._clean_non_negative("kuttal_quantity")

    def clean_kuttal_price(self):
        return self._clean_non_negative("kuttal_price")

    def clean_lunda_quantity(self):
        return self._clean_non_negative("lunda_quantity")

    def clean_lunda_price(self):
        return self._clean_non_negative("lunda_price")

    def clean_fuel_quantity(self):
        return self._clean_non_negative("fuel_quantity")

    def clean_fuel_price(self):
        return self._clean_non_negative("fuel_price")

    def clean(self):
        cleaned = super().clean()
        record_date = cleaned.get("record_date")
        shift = cleaned.get("shift")
        if record_date and shift:
            qs = OilBoilerShiftRecord.objects.filter(
                record_date=record_date,
                shift=shift,
                is_cancelled=False,
                is_deleted=False,
            )
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error(
                    None,
                    f"A record for {record_date} Shift {shift} already exists. "
                    "Open that date and shift to update it.",
                )
        return cleaned
