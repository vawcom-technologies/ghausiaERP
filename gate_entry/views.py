from datetime import date

from django.contrib import messages
from django.db.models import IntegerField
from django.db.models.functions import Cast, Substr
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView, UpdateView

from accounts.mixins import AuditUpdateMixin, ERPLoginRequiredMixin, PaginatedListMixin
from common.excel import build_data_export_response, build_template_response, read_sheet_rows
from common.views import apply_search
from gate_entry.forms import GateEntryForm
from gate_entry.models import GateEntry
from gate_entry.services import (
    GATE_HEADERS,
    entry_to_excel_row,
    next_gate_sequence_start,
    parse_grid_post,
    save_gate_rows,
    sheet_display_rows,
)


class GateEntryListView(ERPLoginRequiredMixin, PaginatedListMixin, ListView):
    model = GateEntry
    template_name = "gate_entry/list.html"
    context_object_name = "objects"

    def get_queryset(self):
        qs = GateEntry.objects.all()
        search = self.request.GET.get("q", "")
        if search:
            qs = apply_search(
                qs,
                search,
                [
                    "gate_number",
                    "purchaser",
                    "shop_name",
                    "demanded_by",
                    "chemical",
                    "electrical",
                    "mechanical",
                    "general",
                ],
            )
        # G1, G2, G3… (numeric order, not newest-first)
        return qs.annotate(
            _gate_seq=Cast(Substr("gate_number", 2), IntegerField())
        ).order_by("_gate_seq", "id")


class GateEntryDetailView(ERPLoginRequiredMixin, DetailView):
    model = GateEntry
    template_name = "gate_entry/detail.html"
    context_object_name = "object"


class GateEntryUpdateView(ERPLoginRequiredMixin, AuditUpdateMixin, UpdateView):
    model = GateEntry
    form_class = GateEntryForm
    template_name = "gate_entry/form.html"

    def get_success_url(self):
        return reverse("gate_entry:list")

    def form_valid(self, form):
        messages.success(
            self.request,
            f"Gate entry {form.instance.gate_number} updated.",
        )
        return super().form_valid(form)


class GateEntryDeleteView(ERPLoginRequiredMixin, View):
    """Soft-delete a gate entry (recoverable from Profile → Recently Deleted)."""

    def post(self, request, pk):
        from common.recycle import soft_delete_record

        entry = get_object_or_404(GateEntry, pk=pk)
        label = entry.gate_number
        soft_delete_record(entry, request.user)
        messages.success(
            request,
            f"Gate entry {label} moved to Recently Deleted. You can restore it from your profile.",
        )
        return redirect("gate_entry:list")


class GateEntrySheetView(ERPLoginRequiredMixin, View):
    """Spreadsheet entry for gate-in stock demands."""

    template_name = "gate_entry/sheet.html"
    blank_rows = 8

    def get(self, request):
        return render(request, self.template_name, self._context())

    def post(self, request):
        rows = parse_grid_post(request.POST, request.FILES)
        saved, errors, failed_indexes = save_gate_rows(rows, request.user)
        if saved:
            messages.success(request, f"Saved {saved} gate entry row(s).")
        if errors:
            for err in errors[:20]:
                messages.error(request, err)
            if len(errors) > 20:
                messages.error(request, f"…and {len(errors) - 20} more error(s).")
            messages.warning(
                request,
                "Your typed values are kept below. Selected photos are kept for those rows. "
                "Fix the highlighted rows and save again.",
            )
        if saved and not errors:
            return redirect("gate_entry:list")

        display_rows = sheet_display_rows(
            rows,
            failed_indexes=failed_indexes or None,
            min_rows=self.blank_rows,
            today=date.today().isoformat(),
            start_seq=next_gate_sequence_start(),
        )
        return render(request, self.template_name, self._context(sheet_rows=display_rows))

    def _context(self, sheet_rows=None):
        today = date.today().isoformat()
        start_seq = next_gate_sequence_start()
        if sheet_rows is None:
            sheet_rows = sheet_display_rows(
                [],
                min_rows=self.blank_rows,
                today=today,
                start_seq=start_seq,
            )
        return {
            "today": today,
            "start_seq": start_seq,
            "sheet_rows": sheet_rows,
        }


class GateEntryTemplateDownloadView(ERPLoginRequiredMixin, View):
    def get(self, request):
        return build_template_response(
            filename="gate_entry_template.xlsx",
            headers=GATE_HEADERS,
            sample_rows=[
                [
                    "",
                    date.today().isoformat(),
                    "Sample Purchaser",
                    "Sample Shop",
                    "1. chemical item",
                    "",
                    "",
                    "1. general item",
                    "Sample Demander",
                ]
            ],
            sheet_title="Gate Entry",
        )


class GateEntryExportView(ERPLoginRequiredMixin, View):
    """Download saved gate entry rows as Excel."""

    def get(self, request):
        qs = GateEntry.objects.annotate(
            _gate_seq=Cast(Substr("gate_number", 2), IntegerField())
        ).order_by("_gate_seq", "id")
        search = request.GET.get("q", "").strip()
        if search:
            qs = apply_search(
                qs,
                search,
                [
                    "gate_number",
                    "purchaser",
                    "shop_name",
                    "demanded_by",
                    "chemical",
                    "electrical",
                    "mechanical",
                    "general",
                ],
            )

        rows = []
        image_paths: list[str | None] = []
        for entry in qs:
            rows.append(entry_to_excel_row(entry))
            if entry.entry_image:
                try:
                    image_paths.append(entry.entry_image.path)
                except (ValueError, OSError):
                    image_paths.append(None)
            else:
                image_paths.append(None)

        return build_data_export_response(
            filename="gate_entry_export.xlsx",
            headers=GATE_HEADERS,
            rows=rows,
            sheet_title="Gate Entry",
            image_paths=image_paths,
            image_column_header="Photo",
        )


class GateEntryImportView(ERPLoginRequiredMixin, View):
    template_name = "gate_entry/import.html"

    def get(self, request):
        return render(request, self.template_name, {"headers": GATE_HEADERS})

    def post(self, request):
        upload = request.FILES.get("excel_file")
        if not upload:
            messages.error(request, "Please choose an Excel (.xlsx) file.")
            return render(request, self.template_name, {"headers": GATE_HEADERS})
        try:
            rows = read_sheet_rows(upload, GATE_HEADERS)
        except ValueError as exc:
            messages.error(request, str(exc))
            return render(request, self.template_name, {"headers": GATE_HEADERS})
        except Exception as exc:  # noqa: BLE001
            messages.error(request, f"Could not read Excel file: {exc}")
            return render(request, self.template_name, {"headers": GATE_HEADERS})

        saved, errors, _failed = save_gate_rows(rows, request.user)
        if saved:
            messages.success(request, f"Imported {saved} gate entry row(s) from Excel.")
        if errors:
            for err in errors[:20]:
                messages.error(request, err)
        if saved and not errors:
            return redirect("gate_entry:list")
        return render(request, self.template_name, {"headers": GATE_HEADERS})


# Keep old name working if anything still points at home
GateEntryHomeView = GateEntrySheetView
