from django import forms

from common.forms import BootstrapFormMixin
from master_data.models import ClothType, Employee, Machine, Material, Vendor


class VendorForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Vendor
        fields = ["name", "contact_person", "phone", "address", "is_active"]


class ClothTypeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ClothType
        fields = ["name", "code", "description", "default_unit", "is_active"]


class EmployeeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Employee
        fields = ["name", "employee_code", "department", "role", "phone", "is_active"]


class MachineForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Machine
        fields = [
            "name", "code", "machine_type", "department",
            "installation_date", "status", "remarks", "is_active",
        ]
        widgets = {"installation_date": forms.DateInput(attrs={"type": "date"})}


class MaterialForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Material
        fields = ["name", "code", "category", "unit", "minimum_stock", "is_active"]
