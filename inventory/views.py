from datetime import date

from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, TemplateView

from accounts.mixins import AuditCreateMixin, ERPLoginRequiredMixin, PaginatedListMixin
from common.excel import build_data_export_response, build_template_response, read_sheet_rows
from common.selective_export import filter_queryset_by_ids, ordered_by_ids, parse_selected_ids
from common.views import apply_search
from inventory.forms import AdjustmentInForm, AdjustmentOutForm, PurchaseForm
from inventory.models import ChemicalIssueSlip, ChemicalStock, MaterialTransaction
from inventory.services.bulk import (
    PURCHASE_HEADERS,
    TRANSACTION_EXPORT_HEADERS,
    parse_purchase_grid_post,
    save_purchase_rows,
    transaction_to_excel_row,
)
from inventory.services.chemicals import (
    ISSUE_SLIP_HEADERS,
    STOCK_HEADERS,
    issue_slip_to_excel_row,
    parse_issue_slip_grid_post,
    parse_stock_grid_post,
    save_issue_slip_rows,
    save_stock_rows,
    sheet_display_rows as issue_slip_sheet_rows,
    stock_sheet_display_rows,
    stock_to_excel_row,
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

    # Nav sections → material categories
    SECTION_CATEGORIES = {
        "chemicals": ("Chemical", "Dye"),
        "mechanical-electrical": ("Mechanical", "Electrical"),
    }
    SECTION_TITLES = {
        "chemicals": "Chemicals Stock",
        "mechanical-electrical": "Mechanical & Electrical Stock",
    }

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        section = self.kwargs.get("section")
        materials = Material.objects.filter(is_active=True).order_by("name")
        if section in self.SECTION_CATEGORIES:
            materials = materials.filter(category__in=self.SECTION_CATEGORIES[section])
            ctx["page_title"] = self.SECTION_TITLES[section]
            ctx["section"] = section
        else:
            ctx["page_title"] = "Current Material Stock"
            ctx["section"] = None
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


class TransactionExportView(ERPLoginRequiredMixin, View):
    """Excel export for material transactions (supports selected ids)."""

    def get(self, request):
        return self._export(request)

    def post(self, request):
        return self._export(request)

    def _export(self, request):
        ids = parse_selected_ids(request)
        if ids is not None and len(ids) == 0:
            messages.error(request, "Select at least one row to export.")
            return redirect("inventory:transaction_list")

        qs = MaterialTransaction.objects.select_related("material").order_by(
            "-transaction_date", "-id"
        )
        search = (request.POST.get("q") or request.GET.get("q") or "").strip()
        if search and ids is None:
            qs = apply_search(qs, search, ["transaction_number", "related_reference"])
        ttype = (request.POST.get("type") or request.GET.get("type") or "").strip()
        if ttype and ids is None:
            qs = qs.filter(transaction_type=ttype)

        qs = filter_queryset_by_ids(qs, ids)
        objects = ordered_by_ids(qs, ids) if ids is not None else list(qs)
        rows = [transaction_to_excel_row(obj) for obj in objects]
        return build_data_export_response(
            filename="material_transactions_export.xlsx",
            headers=TRANSACTION_EXPORT_HEADERS,
            rows=rows,
            sheet_title="Transactions",
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


class ChemicalsHubView(ERPLoginRequiredMixin, TemplateView):
    template_name = "inventory/chemicals_hub.html"


class ChemicalIssueSlipListView(ERPLoginRequiredMixin, PaginatedListMixin, ListView):
    model = ChemicalIssueSlip
    template_name = "inventory/chemical_issue_slip_list.html"
    context_object_name = "objects"

    def get_queryset(self):
        qs = ChemicalIssueSlip.objects.all()
        search = self.request.GET.get("q", "")
        return apply_search(
            qs, search, ["issue_slip_number", "name", "department", "lot_number"]
        ).order_by("-id")


class ChemicalStockListView(ERPLoginRequiredMixin, PaginatedListMixin, ListView):
    model = ChemicalStock
    template_name = "inventory/chemical_stock_list.html"
    context_object_name = "objects"

    def get_queryset(self):
        qs = ChemicalStock.objects.all()
        search = self.request.GET.get("q", "")
        return apply_search(qs, search, ["name", "stock_date"]).order_by("-id")


class ChemicalIssueSlipExportView(ERPLoginRequiredMixin, View):
    def get(self, request):
        return self._export(request)

    def post(self, request):
        return self._export(request)

    def _export(self, request):
        ids = parse_selected_ids(request)
        if ids is not None and len(ids) == 0:
            messages.error(request, "Select at least one row to export.")
            return redirect("inventory:chemical_issue_slip_list")

        qs = ChemicalIssueSlip.objects.order_by("-id")
        search = (request.POST.get("q") or request.GET.get("q") or "").strip()
        if search and ids is None:
            qs = apply_search(
                qs, search, ["issue_slip_number", "name", "department", "lot_number"]
            )
        qs = filter_queryset_by_ids(qs, ids)
        objects = ordered_by_ids(qs, ids) if ids is not None else list(qs)
        return build_data_export_response(
            filename="chemical_issue_slip_export.xlsx",
            headers=ISSUE_SLIP_HEADERS,
            rows=[issue_slip_to_excel_row(obj) for obj in objects],
            sheet_title="Issue Slip",
        )


class ChemicalStockExportView(ERPLoginRequiredMixin, View):
    def get(self, request):
        return self._export(request)

    def post(self, request):
        return self._export(request)

    def _export(self, request):
        ids = parse_selected_ids(request)
        if ids is not None and len(ids) == 0:
            messages.error(request, "Select at least one row to export.")
            return redirect("inventory:chemical_stock_list")

        qs = ChemicalStock.objects.order_by("-id")
        search = (request.POST.get("q") or request.GET.get("q") or "").strip()
        if search and ids is None:
            qs = apply_search(qs, search, ["name", "stock_date"])
        qs = filter_queryset_by_ids(qs, ids)
        objects = ordered_by_ids(qs, ids) if ids is not None else list(qs)
        return build_data_export_response(
            filename="chemical_stock_export.xlsx",
            headers=STOCK_HEADERS,
            rows=[stock_to_excel_row(obj) for obj in objects],
            sheet_title="Chemical Stock",
        )


class ChemicalIssueSlipSheetView(ERPLoginRequiredMixin, View):
    template_name = "inventory/chemical_issue_slip_sheet.html"
    blank_rows = 10

    def get(self, request):
        return render(request, self.template_name, self._context())

    def post(self, request):
        rows = parse_issue_slip_grid_post(request.POST)
        saved, errors, failed_indexes = save_issue_slip_rows(rows, request.user)
        if saved:
            messages.success(request, f"Saved {saved} issue slip row(s).")
        if errors:
            for err in errors[:20]:
                messages.error(request, err)
            if len(errors) > 20:
                messages.error(request, f"…and {len(errors) - 20} more error(s).")
            messages.warning(
                request,
                "Your typed values are kept below. Fix the highlighted rows and save again.",
            )
        if saved and not errors:
            return redirect("inventory:chemical_issue_slip_list")

        display_rows = issue_slip_sheet_rows(
            rows,
            failed_indexes=failed_indexes or None,
            min_rows=self.blank_rows,
            today=date.today().isoformat(),
        )
        return render(request, self.template_name, self._context(sheet_rows=display_rows))

    def _context(self, sheet_rows=None):
        today = date.today().isoformat()
        if sheet_rows is None:
            sheet_rows = issue_slip_sheet_rows([], min_rows=self.blank_rows, today=today)
        return {"today": today, "sheet_rows": sheet_rows}


class ChemicalStockSheetView(ERPLoginRequiredMixin, View):
    """Chemicals stock spreadsheet with auto total / remaining."""

    template_name = "inventory/chemical_stock_sheet.html"
    blank_rows = 10

    def get(self, request):
        return render(request, self.template_name, self._context())

    def post(self, request):
        rows = parse_stock_grid_post(request.POST)
        saved, errors, failed_indexes = save_stock_rows(rows, request.user)
        if saved:
            messages.success(request, f"Saved {saved} chemical stock row(s).")
        if errors:
            for err in errors[:20]:
                messages.error(request, err)
            if len(errors) > 20:
                messages.error(request, f"…and {len(errors) - 20} more error(s).")
            messages.warning(
                request,
                "Your typed values are kept below. Fix the highlighted rows and save again.",
            )
        if saved and not errors:
            return redirect("inventory:chemical_stock_list")

        display_rows = stock_sheet_display_rows(
            rows,
            failed_indexes=failed_indexes or None,
            min_rows=self.blank_rows,
            today=date.today().isoformat(),
        )
        return render(request, self.template_name, self._context(sheet_rows=display_rows))

    def _context(self, sheet_rows=None):
        today = date.today().isoformat()
        if sheet_rows is None:
            sheet_rows = stock_sheet_display_rows([], min_rows=self.blank_rows, today=today)
        return {"today": today, "sheet_rows": sheet_rows}
