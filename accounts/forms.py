from django import forms
from django.contrib.auth.models import User

from accounts.modules import MODULE_CHOICES
from accounts.permissions import GROUP_ADMIN, GROUP_DATA_ENTRY, GROUP_SUPERVISOR, is_administrator


class StaffUserCreateForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={"autocomplete": "username"}),
    )
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    role = forms.ChoiceField(
        choices=(
            (GROUP_DATA_ENTRY, "Data Entry User"),
            (GROUP_SUPERVISOR, "Supervisor"),
            (GROUP_ADMIN, "Administrator"),
        ),
        initial=GROUP_DATA_ENTRY,
    )
    modules = forms.MultipleChoiceField(
        choices=MODULE_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Assigned jobs",
        help_text="Only used for data-entry users. Admin and supervisor can access every area.",
    )

    def __init__(self, *args, creator=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.creator = creator
        for name, field in self.fields.items():
            if name != "modules":
                css = field.widget.attrs.get("class", "")
                field.widget.attrs["class"] = f"{css} form-control".strip()
        self.fields["modules"].widget.attrs["class"] = "form-check-input"
        if creator is None or not is_administrator(creator):
            self.fields["role"].choices = ((GROUP_DATA_ENTRY, "Data Entry User"),)
            self.fields["role"].initial = GROUP_DATA_ENTRY
            self.fields["role"].widget = forms.HiddenInput()

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("That username is already taken.")
        return username

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password1") and cleaned.get("password2"):
            if cleaned["password1"] != cleaned["password2"]:
                self.add_error("password2", "Passwords do not match.")
        if len(cleaned.get("password1") or "") < 6:
            self.add_error("password1", "Use at least 6 characters.")
        if not is_administrator(self.creator) and cleaned.get("role") != GROUP_DATA_ENTRY:
            self.add_error("role", "Supervisors can only create data-entry users.")
        return cleaned
