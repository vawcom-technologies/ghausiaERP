from datetime import date

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import ListView

from accounts.mixins import ERPLoginRequiredMixin, PaginatedListMixin
from common.views import apply_search
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
        return qs.order_by("-entry_date", "-id")


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
