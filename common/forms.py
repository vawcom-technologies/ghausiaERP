"""Bootstrap form styling and alphanumeric entry helpers."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from django import forms


BOOTSTRAP_WIDGET_ATTRS = {"class": "form-control"}
BOOTSTRAP_SELECT_ATTRS = {"class": "form-select"}
BOOTSTRAP_CHECKBOX_ATTRS = {"class": "form-check-input"}

_NUMERIC_FIELD_TYPES = (
    forms.DecimalField,
    forms.IntegerField,
    forms.FloatField,
)

_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
_RESTRICTIVE_ATTRS = ("min", "max", "step", "inputmode", "pattern")


def extract_number_text(value: Any) -> str | None:
    """Pull the first number from free-text / alphanumeric input."""
    if value is None:
        return None
    if isinstance(value, (Decimal, int, float)):
        return str(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        Decimal(text)
        return text
    except InvalidOperation:
        pass
    match = _NUMBER_RE.search(text)
    return match.group(0) if match else None


class FlexibleDecimalField(forms.DecimalField):
    """Accept letters/units in the box; store the numeric portion."""

    def to_python(self, value):
        if value in self.empty_values:
            return None
        if isinstance(value, (Decimal, int, float)):
            return super().to_python(value)
        extracted = extract_number_text(value)
        if extracted is None:
            if str(value).strip() == "":
                return None
            # Pure text with no digits — treat as empty so alphanumeric typing is allowed
            return None
        return super().to_python(extracted)


class FlexibleIntegerField(forms.IntegerField):
    """Accept letters/units in the box; store the integer portion."""

    def to_python(self, value):
        if value in self.empty_values:
            return None
        if isinstance(value, int) and not isinstance(value, bool):
            return super().to_python(value)
        extracted = extract_number_text(value)
        if extracted is None:
            if str(value).strip() == "":
                return None
            return None
        try:
            return super().to_python(int(Decimal(extracted)))
        except (InvalidOperation, ValueError, forms.ValidationError) as exc:
            raise forms.ValidationError("Enter a valid number.", code="invalid") from exc


def _is_zeroish(value) -> bool:
    if value is None or value == "":
        return True
    if value in (0, "0", 0.0):
        return True
    try:
        return Decimal(str(value)) == 0
    except (InvalidOperation, TypeError, ValueError):
        return False


def blank_zero_entry_initials(form) -> None:
    """
    Leave numeric entry fields empty on new forms instead of showing model default 0.
    Skips bound forms, edits of existing rows, and hidden fields.
    """
    if form.is_bound:
        return
    instance = getattr(form, "instance", None)
    if instance is not None and getattr(instance, "pk", None):
        return
    for name, field in form.fields.items():
        if isinstance(field.widget, forms.HiddenInput):
            continue
        if not isinstance(field, _NUMERIC_FIELD_TYPES):
            continue
        current = form.initial.get(name, field.initial)
        if _is_zeroish(current):
            field.initial = None
            form.initial[name] = None
        if field.widget.attrs.get("placeholder") == "0":
            field.widget.attrs.pop("placeholder", None)


def _copy_field_config(src: forms.Field, dest: forms.Field) -> forms.Field:
    dest.required = src.required
    dest.label = src.label
    dest.initial = src.initial
    dest.help_text = src.help_text
    dest.error_messages = src.error_messages
    dest.validators = list(src.validators)
    dest.disabled = src.disabled
    dest.widget = src.widget
    return dest


def use_alphanumeric_entry_fields(form) -> None:
    """
    Let users type letters, numbers, and symbols in value fields.
    Replaces number widgets with text inputs and soft numeric parsing.
    """
    for name, field in list(form.fields.items()):
        widget = field.widget
        if isinstance(widget, forms.HiddenInput):
            continue
        if isinstance(
            widget,
            (
                forms.CheckboxInput,
                forms.Select,
                forms.SelectMultiple,
                forms.Textarea,
                forms.FileInput,
                forms.ClearableFileInput,
                forms.DateInput,
                forms.DateTimeInput,
                forms.TimeInput,
                forms.PasswordInput,
            ),
        ):
            continue

        if isinstance(field, forms.DecimalField) and not isinstance(field, FlexibleDecimalField):
            replacement = FlexibleDecimalField(
                max_digits=getattr(field, "max_digits", None),
                decimal_places=getattr(field, "decimal_places", None),
                max_value=field.max_value,
                min_value=field.min_value,
                localize=field.localize,
            )
            form.fields[name] = _copy_field_config(field, replacement)
            field = form.fields[name]
        elif isinstance(field, forms.IntegerField) and not isinstance(
            field, (FlexibleIntegerField, forms.TypedChoiceField)
        ):
            # Skip choice-backed integer fields (e.g. shift selects)
            if isinstance(widget, (forms.Select, forms.RadioSelect, forms.HiddenInput)):
                continue
            replacement = FlexibleIntegerField(
                max_value=field.max_value,
                min_value=field.min_value,
            )
            form.fields[name] = _copy_field_config(field, replacement)
            field = form.fields[name]
        elif isinstance(field, forms.FloatField):
            replacement = FlexibleDecimalField()
            form.fields[name] = _copy_field_config(field, replacement)
            field = form.fields[name]

        # Force free-text entry (no browser type=number keypad lock)
        if isinstance(field, _NUMERIC_FIELD_TYPES) or isinstance(
            field, (FlexibleDecimalField, FlexibleIntegerField)
        ):
            attrs = {
                k: v
                for k, v in field.widget.attrs.items()
                if k not in _RESTRICTIVE_ATTRS and k != "type"
            }
            attrs.setdefault("class", "form-control")
            attrs["autocomplete"] = attrs.get("autocomplete", "off")
            field.widget = forms.TextInput(attrs=attrs)
        else:
            for key in _RESTRICTIVE_ATTRS:
                if field.widget.attrs.get(key) in ("numeric", "decimal", "number"):
                    field.widget.attrs.pop(key, None)
                elif key in ("min", "max", "step") and isinstance(field.widget, forms.NumberInput):
                    field.widget.attrs.pop(key, None)
            if isinstance(field.widget, forms.NumberInput):
                attrs = {
                    k: v
                    for k, v in field.widget.attrs.items()
                    if k not in _RESTRICTIVE_ATTRS and k != "type"
                }
                attrs.setdefault("class", "form-control")
                field.widget = forms.TextInput(attrs=attrs)
            elif field.widget.attrs.get("inputmode") in ("numeric", "decimal"):
                field.widget.attrs.pop("inputmode", None)


class BootstrapFormMixin:
    """Apply Bootstrap 5 classes and alphanumeric entry widgets."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        use_alphanumeric_entry_fields(self)
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.update(BOOTSTRAP_CHECKBOX_ATTRS)
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs.update(BOOTSTRAP_SELECT_ATTRS)
            elif isinstance(widget, forms.Textarea):
                widget.attrs.update({**BOOTSTRAP_WIDGET_ATTRS, "rows": 3})
            elif not isinstance(widget, forms.HiddenInput):
                widget.attrs.update(BOOTSTRAP_WIDGET_ATTRS)

            if field.required:
                label = field.label or ""
                if not str(label).rstrip().endswith("*"):
                    field.label = f"{label} *"

            if widget.attrs.get("placeholder") == "0":
                widget.attrs.pop("placeholder", None)

        blank_zero_entry_initials(self)
