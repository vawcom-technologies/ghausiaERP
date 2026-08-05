from datetime import date

from django.contrib import messages
from django.db.models import IntegerField
from django.db.models.functions import Cast, Substr
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView, UpdateView

from accounts.mixins import AuditUpdateMixin, ERPLoginRequiredMixin, PaginatedListMixin
from common.views import apply_search
from gate_entry.forms import GateEntryForm
from gate_entry.models import GateEntry
from gate_entry.services import (
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
        rows = parse_grid_post(request.POST)
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
                "Your typed values are kept below. Fix the highlighted rows and save again.",
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


# Keep old name working if anything still points at home
GateEntryHomeView = GateEntrySheetView
