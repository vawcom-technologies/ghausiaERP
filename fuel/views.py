from calendar import month_name
from datetime import date

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from accounts.mixins import ERPLoginRequiredMixin, PaginatedListMixin
from common.views import apply_search
from fuel.forms import OilBoilerShiftForm, SteamBoilerShiftForm
from fuel.models import OilBoilerShiftRecord, SteamBoilerShiftRecord
from fuel.services import (
    oil_boiler_monthly_cumulative,
    parse_month_year,
    shift_month,
    steam_boiler_monthly_cumulative,
)
from fuel.structure import BOILERS, get_boiler


def _parse_boiler_shift(raw, *, model) -> int:
    try:
        shift = int(raw)
    except (TypeError, ValueError):
        return model.SHIFT_1
    if shift in (model.SHIFT_1, model.SHIFT_2):
        return shift
    return model.SHIFT_1


class FuelHubView(ERPLoginRequiredMixin, TemplateView):
    template_name = "fuel/hub.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["boilers"] = BOILERS
        return ctx


class SteamBoilerListView(ERPLoginRequiredMixin, PaginatedListMixin, ListView):
    """Saved steam boiler shift records (like Cloth Receiving list)."""

    model = SteamBoilerShiftRecord
    template_name = "fuel/steam_boiler_list.html"
    context_object_name = "objects"

    def get_queryset(self):
        qs = SteamBoilerShiftRecord.objects.filter(is_cancelled=False)
        search = self.request.GET.get("q", "")
        qs = apply_search(qs, search, ["remarks"])
        return qs.order_by("-record_date", "shift", "-id")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["breadcrumb"] = [
            {"label": "Fuel", "url": reverse("fuel:hub")},
            {"label": "Steam Boiler"},
        ]
        return ctx


class SteamBoilerMonthlyView(ERPLoginRequiredMixin, TemplateView):
    """
    Monthly cumulative Kuttal / Lunda usage by date.
    View resets each calendar month; past months stay in the DB and remain selectable.
    """

    template_name = "fuel/steam_boiler_monthly.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()
        month_start = parse_month_year(
            self.request.GET.get("month"),
            self.request.GET.get("year"),
            today=today,
        )
        report = steam_boiler_monthly_cumulative(month_start)
        prev_m = shift_month(month_start, -1)
        next_m = shift_month(month_start, 1)

        ctx.update(
            {
                "report": report,
                "selected_month": month_start.month,
                "selected_year": month_start.year,
                "month_label": f"{month_name[month_start.month]} {month_start.year}",
                "prev_month": prev_m.month,
                "prev_year": prev_m.year,
                "next_month": next_m.month,
                "next_year": next_m.year,
                "is_current_month": (
                    month_start.year == today.year and month_start.month == today.month
                ),
                "month_choices": list(enumerate(month_name))[1:],
                "year_choices": list(range(today.year - 5, today.year + 2)),
                "breadcrumb": [
                    {"label": "Fuel", "url": reverse("fuel:hub")},
                    {"label": "Steam Boiler", "url": reverse("fuel:steam_boiler")},
                    {"label": "Monthly Cumulative"},
                ],
            }
        )
        return ctx


class SteamBoilerEntryView(ERPLoginRequiredMixin, View):
    """
    Value entry: pick Shift 1 or Shift 2, then enter Kuttal / Lunda
    quantity + price for that day. One saved record per date+shift.
    """

    template_name = "fuel/steam_boiler.html"

    def get(self, request):
        return render(request, self.template_name, self._context(request))

    def post(self, request):
        shift = _parse_boiler_shift(request.POST.get("shift"), model=SteamBoilerShiftRecord)
        record_date = request.POST.get("record_date") or date.today().isoformat()
        existing = (
            SteamBoilerShiftRecord.objects.filter(
                record_date=record_date,
                shift=shift,
                is_cancelled=False,
            ).first()
            if record_date
            else None
        )
        form = SteamBoilerShiftForm(request.POST, instance=existing)
        if form.is_valid():
            obj = form.save(commit=False)
            if existing is None:
                obj.created_by = request.user
            obj.updated_by = request.user
            obj.save()
            messages.success(
                request,
                f"Saved Steam Boiler — {obj.record_date} Shift {obj.shift}.",
            )
            return redirect("fuel:steam_boiler")

        messages.error(request, "Could not save. Check the highlighted fields.")
        return render(
            request,
            self.template_name,
            self._context(request, form=form, shift=shift),
        )

    def _context(self, request, form=None, shift=None):
        boiler = get_boiler("steam-boiler")
        today = date.today().isoformat()
        selected_date = (request.GET.get("date") or today).strip() or today
        if shift is None:
            shift = _parse_boiler_shift(
                request.GET.get("shift") or request.POST.get("shift"),
                model=SteamBoilerShiftRecord,
            )

        existing = SteamBoilerShiftRecord.objects.filter(
            record_date=selected_date,
            shift=shift,
            is_cancelled=False,
        ).first()

        if form is None:
            initial = {
                "record_date": selected_date,
                "shift": shift,
                "remarks": existing.remarks if existing else "",
            }
            if existing:
                initial.update(
                    {
                        "kuttal_quantity": existing.kuttal_quantity,
                        "kuttal_price": existing.kuttal_price,
                        "lunda_quantity": existing.lunda_quantity,
                        "lunda_price": existing.lunda_price,
                    }
                )
            form = SteamBoilerShiftForm(instance=existing, initial=initial)

        return {
            "boiler": boiler,
            "form": form,
            "selected_date": selected_date,
            "selected_shift": shift,
            "existing": existing,
            "breadcrumb": [
                {"label": "Fuel", "url": reverse("fuel:hub")},
                {"label": "Steam Boiler", "url": reverse("fuel:steam_boiler")},
                {"label": "New Entry"},
            ],
        }


# Keep old name as alias for any imports
SteamBoilerView = SteamBoilerEntryView


class SteamBoilerDetailView(ERPLoginRequiredMixin, DetailView):
    model = SteamBoilerShiftRecord
    template_name = "fuel/steam_boiler_detail.html"
    context_object_name = "object"

    def get_queryset(self):
        return SteamBoilerShiftRecord.objects.filter(is_cancelled=False)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["breadcrumb"] = [
            {"label": "Fuel", "url": reverse("fuel:hub")},
            {"label": "Steam Boiler", "url": reverse("fuel:steam_boiler")},
            {"label": f"{self.object.record_date} — Shift {self.object.shift}"},
        ]
        return ctx


class SteamBoilerUpdateRedirectView(ERPLoginRequiredMixin, View):
    """Open the steam boiler entry form preloaded for this record's date + shift."""

    def get(self, request, pk):
        obj = get_object_or_404(SteamBoilerShiftRecord, pk=pk, is_cancelled=False)
        return redirect(
            f"{reverse('fuel:steam_boiler_entry')}?date={obj.record_date}&shift={obj.shift}"
        )


class SteamBoilerDeleteView(ERPLoginRequiredMixin, View):
    """Soft-delete a steam boiler shift record."""

    def post(self, request, pk):
        from accounts.permissions import can_soft_delete_records
        from common.recycle import soft_delete_record
        from django.core.exceptions import PermissionDenied

        if not can_soft_delete_records(request.user):
            raise PermissionDenied
        obj = get_object_or_404(SteamBoilerShiftRecord, pk=pk)
        label = f"{obj.record_date} Shift {obj.shift}"
        soft_delete_record(obj, request.user)
        messages.success(
            request,
            f"Steam boiler record {label} moved to Recently Deleted.",
        )
        return redirect("fuel:steam_boiler")


class OilBoilerListView(ERPLoginRequiredMixin, PaginatedListMixin, ListView):
    """Saved oil boiler shift records."""

    model = OilBoilerShiftRecord
    template_name = "fuel/oil_boiler_list.html"
    context_object_name = "objects"

    def get_queryset(self):
        qs = OilBoilerShiftRecord.objects.filter(is_cancelled=False)
        search = self.request.GET.get("q", "")
        qs = apply_search(qs, search, ["remarks"])
        return qs.order_by("-record_date", "shift", "-id")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["breadcrumb"] = [
            {"label": "Fuel", "url": reverse("fuel:hub")},
            {"label": "Oil Boiler"},
        ]
        return ctx


class OilBoilerMonthlyView(ERPLoginRequiredMixin, TemplateView):
    """Monthly cumulative run time + Kuttal / Lunda / Fuel for oil boiler."""

    template_name = "fuel/oil_boiler_monthly.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()
        month_start = parse_month_year(
            self.request.GET.get("month"),
            self.request.GET.get("year"),
            today=today,
        )
        report = oil_boiler_monthly_cumulative(month_start)
        prev_m = shift_month(month_start, -1)
        next_m = shift_month(month_start, 1)

        ctx.update(
            {
                "report": report,
                "selected_month": month_start.month,
                "selected_year": month_start.year,
                "month_label": f"{month_name[month_start.month]} {month_start.year}",
                "prev_month": prev_m.month,
                "prev_year": prev_m.year,
                "next_month": next_m.month,
                "next_year": next_m.year,
                "is_current_month": (
                    month_start.year == today.year and month_start.month == today.month
                ),
                "month_choices": list(enumerate(month_name))[1:],
                "year_choices": list(range(today.year - 5, today.year + 2)),
                "breadcrumb": [
                    {"label": "Fuel", "url": reverse("fuel:hub")},
                    {"label": "Oil Boiler", "url": reverse("fuel:oil_boiler")},
                    {"label": "Monthly Cumulative"},
                ],
            }
        )
        return ctx


class OilBoilerEntryView(ERPLoginRequiredMixin, View):
    """
    Value entry: Shift 1 / 2 with run time (hours) plus Kuttal, Lunda, Fuel
    quantity + price. One saved record per date+shift.
    """

    template_name = "fuel/oil_boiler.html"

    def get(self, request):
        return render(request, self.template_name, self._context(request))

    def post(self, request):
        shift = _parse_boiler_shift(request.POST.get("shift"), model=OilBoilerShiftRecord)
        record_date = request.POST.get("record_date") or date.today().isoformat()
        existing = (
            OilBoilerShiftRecord.objects.filter(
                record_date=record_date,
                shift=shift,
                is_cancelled=False,
            ).first()
            if record_date
            else None
        )
        form = OilBoilerShiftForm(request.POST, instance=existing)
        if form.is_valid():
            obj = form.save(commit=False)
            if existing is None:
                obj.created_by = request.user
            obj.updated_by = request.user
            obj.save()
            messages.success(
                request,
                f"Saved Oil Boiler — {obj.record_date} Shift {obj.shift}.",
            )
            return redirect("fuel:oil_boiler")

        messages.error(request, "Could not save. Check the highlighted fields.")
        return render(
            request,
            self.template_name,
            self._context(request, form=form, shift=shift),
        )

    def _context(self, request, form=None, shift=None):
        boiler = get_boiler("oil-boiler")
        today = date.today().isoformat()
        selected_date = (request.GET.get("date") or today).strip() or today
        if shift is None:
            shift = _parse_boiler_shift(
                request.GET.get("shift") or request.POST.get("shift"),
                model=OilBoilerShiftRecord,
            )

        existing = OilBoilerShiftRecord.objects.filter(
            record_date=selected_date,
            shift=shift,
            is_cancelled=False,
        ).first()

        if form is None:
            initial = {
                "record_date": selected_date,
                "shift": shift,
                "remarks": existing.remarks if existing else "",
            }
            if existing:
                initial.update(
                    {
                        "run_hours": existing.run_hours,
                        "kuttal_quantity": existing.kuttal_quantity,
                        "kuttal_price": existing.kuttal_price,
                        "lunda_quantity": existing.lunda_quantity,
                        "lunda_price": existing.lunda_price,
                        "fuel_quantity": existing.fuel_quantity,
                        "fuel_price": existing.fuel_price,
                    }
                )
            form = OilBoilerShiftForm(instance=existing, initial=initial)

        return {
            "boiler": boiler,
            "form": form,
            "selected_date": selected_date,
            "selected_shift": shift,
            "existing": existing,
            "breadcrumb": [
                {"label": "Fuel", "url": reverse("fuel:hub")},
                {"label": "Oil Boiler", "url": reverse("fuel:oil_boiler")},
                {"label": "New Entry"},
            ],
        }


class OilBoilerDetailView(ERPLoginRequiredMixin, DetailView):
    model = OilBoilerShiftRecord
    template_name = "fuel/oil_boiler_detail.html"
    context_object_name = "object"

    def get_queryset(self):
        return OilBoilerShiftRecord.objects.filter(is_cancelled=False)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["breadcrumb"] = [
            {"label": "Fuel", "url": reverse("fuel:hub")},
            {"label": "Oil Boiler", "url": reverse("fuel:oil_boiler")},
            {"label": f"{self.object.record_date} — Shift {self.object.shift}"},
        ]
        return ctx


class OilBoilerUpdateRedirectView(ERPLoginRequiredMixin, View):
    def get(self, request, pk):
        obj = get_object_or_404(OilBoilerShiftRecord, pk=pk, is_cancelled=False)
        return redirect(
            f"{reverse('fuel:oil_boiler_entry')}?date={obj.record_date}&shift={obj.shift}"
        )


class OilBoilerDeleteView(ERPLoginRequiredMixin, View):
    def post(self, request, pk):
        from django.core.exceptions import PermissionDenied

        from accounts.permissions import can_soft_delete_records
        from common.recycle import soft_delete_record

        if not can_soft_delete_records(request.user):
            raise PermissionDenied
        obj = get_object_or_404(OilBoilerShiftRecord, pk=pk)
        label = f"{obj.record_date} Shift {obj.shift}"
        soft_delete_record(obj, request.user)
        messages.success(
            request,
            f"Oil boiler record {label} moved to Recently Deleted.",
        )
        return redirect("fuel:oil_boiler")


# Legacy placeholder name (unused once oil URLs point at real views)
FuelBoilerView = OilBoilerListView