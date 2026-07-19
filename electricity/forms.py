from django import forms

from common.forms import BootstrapFormMixin
from electricity.models import DailyElectricityReading, ElectricityMeter
from electricity.services.electricity import calculate_units_consumed, get_latest_closing_reading
from master_data.models import Machine


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
