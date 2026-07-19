from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView, View

from accounts.mixins import (
    AuditCreateMixin,
    AuditUpdateMixin,
    CancelRecordView,
    ERPLoginRequiredMixin,
    PaginatedListMixin,
)
from common.views import apply_search
from inventory.services.stock import reverse_material_transaction
from master_data.forms import ClothTypeForm, EmployeeForm, MachineForm, MaterialForm, VendorForm
from master_data.models import ClothType, Employee, Machine, Material, Vendor


# --- Vendor ---
class VendorListView(ERPLoginRequiredMixin, PaginatedListMixin, ListView):
    model = Vendor
    template_name = "master_data/list.html"
    context_object_name = "objects"

    def get_queryset(self):
        return apply_search(Vendor.objects.all(), self.request.GET.get("q", ""), ["name", "phone"])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({"model_name": "Vendors", "create_url": "master_data:vendor_create", "detail_url": "master_data:vendor_detail", "edit_url": "master_data:vendor_edit"})
        return ctx


class VendorCreateView(ERPLoginRequiredMixin, AuditCreateMixin, CreateView):
    model = Vendor
    form_class = VendorForm
    template_name = "master_data/form.html"
    success_url = reverse_lazy("master_data:vendor_list")

    def form_valid(self, form):
        messages.success(self.request, "Vendor saved successfully.")
        return super().form_valid(form)


class VendorUpdateView(ERPLoginRequiredMixin, AuditUpdateMixin, UpdateView):
    model = Vendor
    form_class = VendorForm
    template_name = "master_data/form.html"

    def get_success_url(self):
        return reverse("master_data:vendor_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, "Vendor updated successfully.")
        return super().form_valid(form)


class VendorDetailView(ERPLoginRequiredMixin, DetailView):
    model = Vendor
    template_name = "master_data/detail.html"


# --- ClothType ---
class ClothTypeListView(ERPLoginRequiredMixin, PaginatedListMixin, ListView):
    model = ClothType
    template_name = "master_data/list.html"
    context_object_name = "objects"

    def get_queryset(self):
        return apply_search(ClothType.objects.all(), self.request.GET.get("q", ""), ["name", "code"])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({"model_name": "Cloth Types", "create_url": "master_data:clothtype_create", "detail_url": "master_data:clothtype_detail", "edit_url": "master_data:clothtype_edit"})
        return ctx


class ClothTypeCreateView(ERPLoginRequiredMixin, AuditCreateMixin, CreateView):
    model = ClothType
    form_class = ClothTypeForm
    template_name = "master_data/form.html"
    success_url = reverse_lazy("master_data:clothtype_list")

    def form_valid(self, form):
        messages.success(self.request, "Cloth type saved successfully.")
        return super().form_valid(form)


class ClothTypeUpdateView(ERPLoginRequiredMixin, AuditUpdateMixin, UpdateView):
    model = ClothType
    form_class = ClothTypeForm
    template_name = "master_data/form.html"

    def get_success_url(self):
        return reverse("master_data:clothtype_detail", kwargs={"pk": self.object.pk})


class ClothTypeDetailView(ERPLoginRequiredMixin, DetailView):
    model = ClothType
    template_name = "master_data/detail.html"


# --- Employee ---
class EmployeeListView(ERPLoginRequiredMixin, PaginatedListMixin, ListView):
    model = Employee
    template_name = "master_data/list.html"
    context_object_name = "objects"

    def get_queryset(self):
        return apply_search(Employee.objects.all(), self.request.GET.get("q", ""), ["name", "employee_code"])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({"model_name": "Employees", "create_url": "master_data:employee_create", "detail_url": "master_data:employee_detail", "edit_url": "master_data:employee_edit"})
        return ctx


class EmployeeCreateView(ERPLoginRequiredMixin, AuditCreateMixin, CreateView):
    model = Employee
    form_class = EmployeeForm
    template_name = "master_data/form.html"
    success_url = reverse_lazy("master_data:employee_list")


class EmployeeUpdateView(ERPLoginRequiredMixin, AuditUpdateMixin, UpdateView):
    model = Employee
    form_class = EmployeeForm
    template_name = "master_data/form.html"

    def get_success_url(self):
        return reverse("master_data:employee_detail", kwargs={"pk": self.object.pk})


class EmployeeDetailView(ERPLoginRequiredMixin, DetailView):
    model = Employee
    template_name = "master_data/detail.html"


# --- Machine ---
class MachineListView(ERPLoginRequiredMixin, PaginatedListMixin, ListView):
    model = Machine
    template_name = "master_data/list.html"
    context_object_name = "objects"

    def get_queryset(self):
        qs = Machine.objects.all()
        search = self.request.GET.get("q", "")
        qs = apply_search(qs, search, ["name", "code"])
        mtype = self.request.GET.get("type", "")
        if mtype:
            qs = qs.filter(machine_type=mtype)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({"model_name": "Machines", "create_url": "master_data:machine_create", "detail_url": "master_data:machine_detail", "edit_url": "master_data:machine_edit"})
        return ctx


class MachineCreateView(ERPLoginRequiredMixin, AuditCreateMixin, CreateView):
    model = Machine
    form_class = MachineForm
    template_name = "master_data/form.html"
    success_url = reverse_lazy("master_data:machine_list")


class MachineUpdateView(ERPLoginRequiredMixin, AuditUpdateMixin, UpdateView):
    model = Machine
    form_class = MachineForm
    template_name = "master_data/form.html"

    def get_success_url(self):
        return reverse("master_data:machine_detail", kwargs={"pk": self.object.pk})


class MachineDetailView(ERPLoginRequiredMixin, DetailView):
    model = Machine
    template_name = "master_data/detail.html"


# --- Material ---
class MaterialListView(ERPLoginRequiredMixin, PaginatedListMixin, ListView):
    model = Material
    template_name = "master_data/material_list.html"
    context_object_name = "objects"

    def get_queryset(self):
        return apply_search(Material.objects.all(), self.request.GET.get("q", ""), ["name", "code"])

    def get_context_data(self, **kwargs):
        from inventory.services.stock import get_material_stock

        ctx = super().get_context_data(**kwargs)
        ctx["items"] = [
            {"material": m, "stock": get_material_stock(m.id)} for m in ctx["objects"]
        ]
        ctx.update({"model_name": "Materials", "create_url": "master_data:material_create", "detail_url": "master_data:material_detail", "edit_url": "master_data:material_edit"})
        return ctx


class MaterialCreateView(ERPLoginRequiredMixin, AuditCreateMixin, CreateView):
    model = Material
    form_class = MaterialForm
    template_name = "master_data/form.html"
    success_url = reverse_lazy("master_data:material_list")


class MaterialUpdateView(ERPLoginRequiredMixin, AuditUpdateMixin, UpdateView):
    model = Material
    form_class = MaterialForm
    template_name = "master_data/form.html"

    def get_success_url(self):
        return reverse("master_data:material_detail", kwargs={"pk": self.object.pk})


class MaterialDetailView(ERPLoginRequiredMixin, DetailView):
    model = Material
    template_name = "master_data/material_detail.html"

    def get_context_data(self, **kwargs):
        from inventory.services.stock import get_material_stock
        from inventory.models import MaterialTransaction

        ctx = super().get_context_data(**kwargs)
        ctx["current_stock"] = get_material_stock(self.object.id)
        ctx["transactions"] = MaterialTransaction.objects.filter(
            material=self.object, is_cancelled=False
        ).order_by("-transaction_date")[:20]
        return ctx


class SetupHomeView(ERPLoginRequiredMixin, TemplateView):
    template_name = "master_data/setup_home.html"
