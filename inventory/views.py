from datetime import date

from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, TemplateView

from accounts.mixins import AuditCreateMixin, ERPLoginRequiredMixin, PaginatedListMixin
from common.excel import build_template_response, read_sheet_rows
from common.views import apply_search
from inventory.forms import AdjustmentInForm, AdjustmentOutForm, PurchaseForm
from inventory.models import MaterialTransaction
from inventory.services.bulk import (
    PURCHASE_HEADERS,
    parse_purchase_grid_post,
    save_purchase_rows,
)
from inventory.services.stock import get_material_stock
from master_data.models import Material


class MaterialTransactionListView(ERPLoginRequiredMixin, PaginatedListMixin, ListView):
    model = MaterialTransaction
    template_name = "inventory/transaction_list.html"
    context_object_name = "objects"

    def get_queryset(self):
        qs = MaterialTransaction.objects.select_related("material")
        search = self.request.GET.get("q", "")
        qs = apply_search(qs, search, ["transaction_number", "related_reference"])
        ttype = self.request.GET.get("type", "")
        if ttype:
            qs = qs.filter(transaction_type=ttype)
        return qs.order_by("-transaction_date")


class MaterialTransactionDetailView(ERPLoginRequiredMixin, DetailView):
    model = MaterialTransaction
    template_name = "inventory/transaction_detail.html"


class PurchaseCreateView(ERPLoginRequiredMixin, AuditCreateMixin, CreateView):
    model = MaterialTransaction
    form_class = PurchaseForm
    template_name = "inventory/form.html"
    success_url = reverse_lazy("inventory:transaction_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        form.instance.entered_by = self.request.user
        form.save()
        messages.success(self.request, "Purchase recorded.")
        return redirect(self.success_url)


class AdjustmentInCreateView(PurchaseCreateView):
    form_class = AdjustmentInForm

    def form_valid(self, form):
        messages.success(self.request, "Stock adjustment (in) recorded.")
        return super(PurchaseCreateView, self).form_valid(form)


class AdjustmentOutCreateView(PurchaseCreateView):
    form_class = AdjustmentOutForm

    def form_valid(self, form):
        messages.success(self.request, "Stock adjustment (out) recorded.")
        return super(PurchaseCreateView, self).form_valid(form)


class StockOverviewView(ERPLoginRequiredMixin, TemplateView):
    template_name = "inventory/stock_overview.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        materials = Material.objects.filter(is_active=True).order_by("name")
        ctx["materials"] = [
            {"material": m, "stock": get_material_stock(m.id)} for m in materials
        ]
        return ctx


class InventoryHomeView(ERPLoginRequiredMixin, TemplateView):
    template_name = "inventory/home.html"


class PurchaseSheetView(ERPLoginRequiredMixin, View):
    template_name = "inventory/purchase_sheet.html"
    blank_rows = 10

    def get(self, request):
        return render(request, self.template_name, self._context())

    def post(self, request):
        rows = parse_purchase_grid_post(request.POST)
        saved, errors = save_purchase_rows(rows, request.user)
        if saved:
            messages.success(request, f"Saved {saved} purchase row(s).")
        if errors:
            for err in errors[:20]:
                messages.error(request, err)
            if len(errors) > 20:
                messages.error(request, f"…and {len(errors) - 20} more error(s).")
        if saved and not errors:
            return redirect("inventory:transaction_list")
        return render(request, self.template_name, self._context())

    def _context(self):
        materials = Material.objects.filter(is_active=True).order_by("name")
        return {
            "materials": materials,
            "today": date.today().isoformat(),
            "row_range": range(self.blank_rows),
            "unit_choices": Material.UNIT_CHOICES,
        }


class PurchaseTemplateDownloadView(ERPLoginRequiredMixin, View):
    def get(self, request):
        return build_template_response(
            filename="material_purchase_template.xlsx",
            headers=PURCHASE_HEADERS,
            sample_rows=[
                [date.today().isoformat(), "Caustic Soda", 25, "Kilogram", "PO-001", ""],
            ],
            sheet_title="Purchases",
        )


class PurchaseImportView(ERPLoginRequiredMixin, View):
    template_name = "inventory/purchase_import.html"

    def get(self, request):
        return render(request, self.template_name, {"headers": PURCHASE_HEADERS})

    def post(self, request):
        upload = request.FILES.get("excel_file")
        if not upload:
            messages.error(request, "Please choose an Excel (.xlsx) file.")
            return render(request, self.template_name, {"headers": PURCHASE_HEADERS})
        try:
            rows = read_sheet_rows(upload, PURCHASE_HEADERS)
        except ValueError as exc:
            messages.error(request, str(exc))
            return render(request, self.template_name, {"headers": PURCHASE_HEADERS})
        except Exception as exc:  # noqa: BLE001
            messages.error(request, f"Could not read Excel file: {exc}")
            return render(request, self.template_name, {"headers": PURCHASE_HEADERS})

        saved, errors = save_purchase_rows(rows, request.user)
        if saved:
            messages.success(request, f"Imported {saved} purchase row(s) from Excel.")
        if errors:
            for err in errors[:20]:
                messages.error(request, err)
        if saved and not errors:
            return redirect("inventory:transaction_list")
        return render(request, self.template_name, {"headers": PURCHASE_HEADERS})
