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
from common.selective_export import selective_excel_response
from common.views import apply_search
from inventory.services.stock import reverse_material_transaction
from master_data.forms import ClothTypeForm, EmployeeForm, MachineForm, MaterialForm, VendorForm
from master_data.models import ClothType, Employee, Machine, Material, Vendor


def _master_export_view(model, headers, row_builder, filename, sheet_title, list_name, search_fields):
    class ExportView(ERPLoginRequiredMixin, View):
        def get(self, request):
            return self._export(request)

        def post(self, request):
            return self._export(request)

        def _export(self, request):
            qs = model.objects.all().order_by("id")
            search = (request.POST.get("q") or request.GET.get("q") or "").strip()
            if search:
                qs = apply_search(qs, search, search_fields)
            return selective_excel_response(
                request,
                queryset=qs,
                headers=headers,
                row_builder=row_builder,
                filename=filename,
                sheet_title=sheet_title,
                list_redirect=list_name,
            )

    return ExportView


# --- Vendor ---
class VendorListView(ERPLoginRequiredMixin, PaginatedListMixin, ListView):
    model = Vendor
    template_name = "master_data/list.html"
    context_object_name = "objects"

    def get_queryset(self):
        return apply_search(Vendor.objects.all(), self.request.GET.get("q", ""), ["name", "phone"])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({
            "model_name": "Vendors",
            "create_url": "master_data:vendor_create",
            "detail_url": "master_data:vendor_detail",
            "edit_url": "master_data:vendor_edit",
            "export_url": "master_data:vendor_export",
        })
        return ctx


VendorExportView = _master_export_view(
    Vendor,
    ["Name", "Contact Person", "Phone", "Address", "Active"],
    lambda o: [o.name, o.contact_person, o.phone, o.address, "Yes" if o.is_active else "No"],
    "vendors_export.xlsx",
    "Vendors",
    "master_data:vendor_list",
    ["name", "phone"],
)


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
        ctx.update({
            "model_name": "Cloth Types",
            "create_url": "master_data:clothtype_create",
            "detail_url": "master_data:clothtype_detail",
            "edit_url": "master_data:clothtype_edit",
            "export_url": "master_data:clothtype_export",
        })
        return ctx


ClothTypeExportView = _master_export_view(
    ClothType,
    ["Name", "Code", "Default Unit", "Description", "Active"],
    lambda o: [o.name, o.code, o.default_unit, o.description, "Yes" if o.is_active else "No"],
    "cloth_types_export.xlsx",
    "Cloth Types",
    "master_data:clothtype_list",
    ["name", "code"],
)


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
        ctx.update({
            "model_name": "Employees",
            "create_url": "master_data:employee_create",
            "detail_url": "master_data:employee_detail",
            "edit_url": "master_data:employee_edit",
            "export_url": "master_data:employee_export",
        })
        return ctx


EmployeeExportView = _master_export_view(
    Employee,
    ["Name", "Code", "Department", "Role", "Phone", "Active"],
    lambda o: [o.name, o.employee_code, o.department, o.role, o.phone, "Yes" if o.is_active else "No"],
    "employees_export.xlsx",
    "Employees",
    "master_data:employee_list",
    ["name", "employee_code"],
)


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
        ctx.update({
            "model_name": "Machines",
            "create_url": "master_data:machine_create",
            "detail_url": "master_data:machine_detail",
            "edit_url": "master_data:machine_edit",
            "export_url": "master_data:machine_export",
        })
        return ctx


MachineExportView = _master_export_view(
    Machine,
    ["Name", "Code", "Type", "Department", "Status", "Active"],
    lambda o: [o.name, o.code, o.machine_type, o.department, o.status, "Yes" if o.is_active else "No"],
    "machines_export.xlsx",
    "Machines",
    "master_data:machine_list",
    ["name", "code"],
)


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
        ctx.update({
            "model_name": "Materials",
            "create_url": "master_data:material_create",
            "detail_url": "master_data:material_detail",
            "edit_url": "master_data:material_edit",
            "export_url": "master_data:material_export",
        })
        return ctx


MaterialExportView = _master_export_view(
    Material,
    ["Name", "Code", "Category", "Unit", "Minimum Stock", "Active"],
    lambda o: [
        o.name,
        o.code,
        o.category,
        o.unit,
        str(o.minimum_stock),
        "Yes" if o.is_active else "No",
    ],
    "materials_export.xlsx",
    "Materials",
    "master_data:material_list",
    ["name", "code"],
)


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
