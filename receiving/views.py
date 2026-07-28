from datetime import date

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from accounts.mixins import (
    AuditCreateMixin,
    AuditUpdateMixin,
    CancelRecordView,
    ERPLoginRequiredMixin,
    PaginatedListMixin,
)
from common.excel import build_data_export_response, build_template_response, read_sheet_rows
from common.views import apply_search
from master_data.models import ClothType, Vendor
from receiving.forms import ClothReceiptForm
from receiving.models import ClothReceipt
from receiving.services.bulk import (
    RECEIVING_HEADERS,
    parse_grid_post,
    receipt_to_excel_row,
    save_receiving_rows,
    sheet_display_rows,
)


class ClothReceiptListView(ERPLoginRequiredMixin, PaginatedListMixin, ListView):
    model = ClothReceipt
    template_name = "receiving/list.html"
    context_object_name = "objects"

    def get_queryset(self):
        qs = ClothReceipt.objects.select_related("vendor", "cloth_type")
        search = self.request.GET.get("q", "")
        if search:
            qs = apply_search(
                qs, search, ["receipt_number", "production_lot_number", "vendor_challan_number"]
            )
            qs = qs | ClothReceipt.objects.filter(vendor__name__icontains=search)
        return qs.distinct().order_by("-receipt_date")


class ClothReceiptCreateView(ERPLoginRequiredMixin, AuditCreateMixin, CreateView):
    model = ClothReceipt
    form_class = ClothReceiptForm
    template_name = "receiving/form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse("receiving:detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        self.object = form.save(user=self.request.user)
        messages.success(
            self.request,
            "Cloth receiving saved. Production lot / palli created.",
        )
        return redirect(self.get_success_url())


class ClothReceiptUpdateView(ERPLoginRequiredMixin, AuditUpdateMixin, UpdateView):
    model = ClothReceipt
    form_class = ClothReceiptForm
    template_name = "receiving/form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse("receiving:detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        form.save(user=self.request.user)
        messages.success(self.request, "Cloth receiving updated.")
        return redirect(self.get_success_url())


class ClothReceiptDetailView(ERPLoginRequiredMixin, DetailView):
    model = ClothReceipt
    template_name = "receiving/detail.html"


class ClothReceiptCancelView(CancelRecordView):
    cancel_url_name = "receiving:cancel"

    def get_object(self):
        return get_object_or_404(ClothReceipt, pk=self.kwargs["pk"])

    def get_success_url(self):
        return reverse("receiving:detail", kwargs={"pk": self.object.pk})


class ReceivingSheetView(ERPLoginRequiredMixin, View):
    """Excel-like multi-row cloth receiving entry."""

    template_name = "receiving/sheet.html"
    blank_rows = 10

    def get(self, request):
        return render(request, self.template_name, self._context())

    def post(self, request):
        rows = parse_grid_post(request.POST, request.FILES)
        saved, errors, failed_indexes = save_receiving_rows(rows, request.user)
        if saved:
            messages.success(request, f"Saved {saved} receiving row(s).")
        if errors:
            for err in errors[:20]:
                messages.error(request, err)
            if len(errors) > 20:
                messages.error(request, f"…and {len(errors) - 20} more error(s).")
            messages.warning(
                request,
                "Your typed values are kept below. Fix the highlighted rows and save again. "
                "Selected photos are kept for those rows.",
            )
        if saved and not errors:
            return redirect("receiving:list")

        # Keep typed values on screen — incomplete rows are not written to the database.
        display_rows = sheet_display_rows(
            rows,
            failed_indexes=failed_indexes or None,
            min_rows=self.blank_rows,
            today=date.today().isoformat(),
        )
        return render(
            request,
            self.template_name,
            self._context(sheet_rows=display_rows),
        )

    def _context(self, sheet_rows=None):
        today = date.today().isoformat()
        if sheet_rows is None:
            sheet_rows = sheet_display_rows([], min_rows=self.blank_rows, today=today)
        return {
            "cloth_types": ClothType.objects.filter(is_active=True).order_by("name"),
            "vendors": Vendor.objects.filter(is_active=True).order_by("name"),
            "today": today,
            "sheet_rows": sheet_rows,
        }


class ReceivingTemplateDownloadView(ERPLoginRequiredMixin, View):
    def get(self, request):
        return build_template_response(
            filename="cloth_receiving_template.xlsx",
            headers=RECEIVING_HEADERS,
            sample_rows=[
                [
                    "LOT-SAMPLE-001",
                    date.today().isoformat(),
                    "Sample Party",
                    "80/40",
                    "/",
                    10,
                    10,
                    "1000",
                    "980",
                    "500",
                    "480",
                    "Sample remarks",
                ]
            ],
            sheet_title="Cloth Receiving",
        )


class ReceivingExportView(ERPLoginRequiredMixin, View):
    """Download all saved cloth receiving rows as Excel (values + photos)."""

    def get(self, request):
        qs = (
            ClothReceipt.objects.select_related("vendor")
            .order_by("-receipt_date", "-id")
        )
        search = request.GET.get("q", "").strip()
        if search:
            qs = apply_search(
                qs, search, ["receipt_number", "production_lot_number", "vendor_challan_number"]
            )
            qs = qs | ClothReceipt.objects.filter(vendor__name__icontains=search)
            qs = qs.distinct().order_by("-receipt_date", "-id")

        rows = []
        image_paths: list[str | None] = []
        for receipt in qs:
            rows.append(receipt_to_excel_row(receipt))
            if receipt.receipt_image:
                try:
                    image_paths.append(receipt.receipt_image.path)
                except (ValueError, OSError):
                    image_paths.append(None)
            else:
                image_paths.append(None)

        return build_data_export_response(
            filename="cloth_receiving_export.xlsx",
            headers=RECEIVING_HEADERS,
            rows=rows,
            sheet_title="Cloth Receiving",
            image_paths=image_paths,
            image_column_header="Photo",
        )


class ReceivingImportView(ERPLoginRequiredMixin, View):
    template_name = "receiving/import.html"

    def get(self, request):
        return render(request, self.template_name, {"headers": RECEIVING_HEADERS})

    def post(self, request):
        upload = request.FILES.get("excel_file")
        if not upload:
            messages.error(request, "Please choose an Excel (.xlsx) file.")
            return render(request, self.template_name, {"headers": RECEIVING_HEADERS})
        try:
            rows = read_sheet_rows(upload, RECEIVING_HEADERS)
        except ValueError as exc:
            messages.error(request, str(exc))
            return render(request, self.template_name, {"headers": RECEIVING_HEADERS})
        except Exception as exc:  # noqa: BLE001
            messages.error(request, f"Could not read Excel file: {exc}")
            return render(request, self.template_name, {"headers": RECEIVING_HEADERS})

        saved, errors, _failed = save_receiving_rows(rows, request.user)
        if saved:
            messages.success(request, f"Imported {saved} receiving row(s) from Excel.")
        if errors:
            for err in errors[:20]:
                messages.error(request, err)
        if saved and not errors:
            return redirect("receiving:list")
        return render(request, self.template_name, {"headers": RECEIVING_HEADERS})
