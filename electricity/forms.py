from decimal import Decimal, InvalidOperation

from django import forms

from common.forms import BootstrapFormMixin, blank_zero_entry_initials
from electricity.models import DailyElectricityReading, DailyPowerReading, ElectricityMeter
from electricity.services.electricity import calculate_units_consumed, get_latest_closing_reading
from master_data.models import Machine

_TEXT_ATTRS = {"class": "form-control", "autocomplete": "off", "inputmode": "decimal"}


class ElectricityMeterForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ElectricityMeter
        fields = ["name", "meter_number", "department", "machine", "multiplier", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["machine"].queryset = Machine.objects.filter(is_active=True)


class DailyElectricityReadingForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = DailyElectricityReading
        fields = [
            "reading_date", "meter", "opening_reading", "closing_reading",
            "multiplier", "checked_by", "remarks",
        ]
        widgets = {"reading_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["meter"].queryset = ElectricityMeter.objects.filter(is_active=True)
        meter_id = self.data.get("meter") or self.initial.get("meter")
        if meter_id and not self.instance.pk:
            meter = ElectricityMeter.objects.filter(pk=meter_id).first()
            if meter:
                self.fields["multiplier"].initial = meter.multiplier
                latest = get_latest_closing_reading(meter.id)
                if latest is not None:
                    self.fields["opening_reading"].initial = latest

    def clean(self):
        cleaned = super().clean()
        opening = cleaned.get("opening_reading")
        closing = cleaned.get("closing_reading")
        multiplier = cleaned.get("multiplier")
        if opening is not None and closing is not None and multiplier is not None:
            cleaned["units_consumed"] = calculate_units_consumed(opening, closing, multiplier)
        return cleaned

    def save(self, commit=True, user=None):
        instance = super().save(commit=False)
        instance.entered_by = user
        instance.calculate_units()
        if commit:
            instance.save()
        return instance


class DailyPowerReadingForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = DailyPowerReading
        fields = [
            "record_date",
            "source_mode",
            "wapda_peak_kwh",
            "wapda_offpeak_kwh",
            "solar_kwh",
            "peak_hours",
            "offpeak_hours",
            "remarks",
        ]
        widgets = {
            "record_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control", "required": True}
            ),
            "source_mode": forms.HiddenInput(),
            "wapda_peak_kwh": forms.TextInput(attrs=_TEXT_ATTRS),
            "wapda_offpeak_kwh": forms.TextInput(attrs=_TEXT_ATTRS),
            "solar_kwh": forms.TextInput(attrs=_TEXT_ATTRS),
            "peak_hours": forms.TextInput(attrs=_TEXT_ATTRS),
            "offpeak_hours": forms.TextInput(attrs=_TEXT_ATTRS),
            "remarks": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Optional remarks"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        blank_zero_entry_initials(self)

    def _clean_non_negative(self, field_name: str) -> Decimal:
        value = self.cleaned_data.get(field_name)
        if value is None or value == "":
            return Decimal("0")
        try:
            qty = Decimal(str(value))
        except (InvalidOperation, TypeError) as exc:
            raise forms.ValidationError("Enter a valid number.") from exc
        if qty < 0:
            raise forms.ValidationError("Value cannot be negative.")
        return qty

    def clean_wapda_peak_kwh(self):
        return self._clean_non_negative("wapda_peak_kwh")

    def clean_wapda_offpeak_kwh(self):
        return self._clean_non_negative("wapda_offpeak_kwh")

    def clean_solar_kwh(self):
        return self._clean_non_negative("solar_kwh")

    def clean_peak_hours(self):
        hours = self._clean_non_negative("peak_hours")
        if hours > Decimal("24"):
            raise forms.ValidationError("Peak hours cannot be more than 24.")
        return hours

    def clean_offpeak_hours(self):
        hours = self._clean_non_negative("offpeak_hours")
        if hours > Decimal("24"):
            raise forms.ValidationError("Non-peak hours cannot be more than 24.")
        return hours

    def clean_source_mode(self):
        mode = self.cleaned_data.get("source_mode")
        if mode not in (DailyPowerReading.MODE_WAPDA, DailyPowerReading.MODE_WAPDA_SOLAR):
            raise forms.ValidationError("Choose WAPDA only or WAPDA + Solar.")
        return mode

    def clean(self):
        cleaned = super().clean()
        record_date = cleaned.get("record_date")
        peak_h = cleaned.get("peak_hours") or Decimal("0")
        offpeak_h = cleaned.get("offpeak_hours") or Decimal("0")
        if peak_h + offpeak_h > Decimal("24"):
            raise forms.ValidationError("Peak and non-peak hours together cannot be more than 24.")
        if cleaned.get("source_mode") != DailyPowerReading.MODE_WAPDA_SOLAR:
            cleaned["solar_kwh"] = Decimal("0")
        if record_date and not self.instance.pk:
            exists = DailyPowerReading.objects.filter(
                record_date=record_date,
                is_cancelled=False,
            ).exists()
            if exists:
                raise forms.ValidationError(
                    "A reading for this date is already saved. Open it from Daily readings to update."
                )
        return cleaned
