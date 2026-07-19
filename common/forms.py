"""Bootstrap form styling helpers."""

from django import forms


BOOTSTRAP_WIDGET_ATTRS = {"class": "form-control"}
BOOTSTRAP_SELECT_ATTRS = {"class": "form-select"}
BOOTSTRAP_CHECKBOX_ATTRS = {"class": "form-check-input"}


class BootstrapFormMixin:
    """Apply Bootstrap 5 classes to form fields."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
                field.label = f"{field.label} *"
