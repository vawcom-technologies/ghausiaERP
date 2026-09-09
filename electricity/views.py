from calendar import month_name
from datetime import date

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from accounts.mixins import AuditCreateMixin, CancelRecordView, ERPLoginRequiredMixin, PaginatedListMixin
from accounts.permissions import can_soft_delete_records
from common.selective_export import selective_excel_response
from common.views import apply_search
from electricity.forms import DailyElectricityReadingForm, DailyPowerReadingForm, ElectricityMeterForm
from electricity.models import DailyElectricityReading, DailyPowerReading, ElectricityMeter
from electricity.services.electricity import monthly_power_report, parse_month_year, shift_month

READING_EXPORT_HEADERS = [
    "Date",
    "Meter",
    "Opening",
    "Closing",
    "Multiplier",
    "Units",
    "Entered By",
    "Remarks",
]


def _reading_excel_row(obj: DailyElectricityReading) -> list:
    return [
        obj.reading_date.isoformat() if obj.reading_date else "",
        str(obj.meter) if obj.meter_id else "",
        str(obj.opening_reading),
        str(obj.closing_reading),
        str(obj.multiplier),
        str(obj.units_consumed),
        str(obj.entered_by) if obj.entered_by_id else "",
        obj.remarks or "",
    ]


class ElectricityMeterListView(ERPLoginRequiredMixin, PaginatedListMixin, ListView):
    model = ElectricityMeter
    template_name = "electricity/meter_list.html"
    context_object_name = "objects"

    def get_queryset(self):
        return apply_search(ElectricityMeter.objects.all(), self.request.GET.get("q", ""), ["name", "meter_number"])


class ElectricityMeterCreateView(ERPLoginRequiredMixin, CreateView):
    model = ElectricityMeter
    form_class = ElectricityMeterForm
    template_name = "electricity/meter_form.html"
    success_url = reverse_lazy("electricity:meter_list")

    def form_valid(self, form):
        messages.success(self.request, "Electricity meter saved.")
        return super().form_valid(form)


class ElectricityMeterUpdateView(ERPLoginRequiredMixin, UpdateView):
    model = ElectricityMeter
    form_class = ElectricityMeterForm
    template_name = "electricity/meter_form.html"
    success_url = reverse_lazy("electricity:meter_list")

    def form_valid(self, form):
        messages.success(self.request, "Electricity meter updated.")
        return super().form_valid(form)


class ElectricityReadingListView(ERPLoginRequiredMixin, PaginatedListMixin, ListView):
    model = DailyElectricityReading
    template_name = "electricity/reading_list.html"
    context_object_name = "objects"

    def get_queryset(self):
        qs = DailyElectricityReading.objects.select_related("meter")
        search = self.request.GET.get("q", "")
        if search:
            qs = qs.filter(meter__name__icontains=search)
        return qs.order_by("-reading_date")


class ElectricityReadingExportView(ERPLoginRequiredMixin, View):
    def get(self, request):
        return self._export(request)

    def post(self, request):
        return self._export(request)

    def _export(self, request):
        qs = DailyElectricityReading.objects.select_related("meter").order_by("-reading_date", "-id")
        search = (request.POST.get("q") or request.GET.get("q") or "").strip()
        if search:
            qs = qs.filter(meter__name__icontains=search)
        return selective_excel_response(
            request,
            queryset=qs,
            headers=READING_EXPORT_HEADERS,
            row_builder=_reading_excel_row,
            filename="electricity_readings_export.xlsx",
            sheet_title="Readings",
            list_redirect="electricity:reading_list",
            today_field="reading_date",
        )


class ElectricityReadingCreateView(ERPLoginRequiredMixin, AuditCreateMixin, CreateView):
    model = DailyElectricityReading
    form_class = DailyElectricityReadingForm
    template_name = "electricity/reading_form.html"
    success_url = reverse_lazy("electricity:reading_list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        form.save(user=self.request.user)
        messages.success(self.request, "Electricity reading saved.")
        return redirect(self.success_url)


class ElectricityReadingDetailView(ERPLoginRequiredMixin, DetailView):
    model = DailyElectricityReading
    template_name = "electricity/reading_detail.html"


class ElectricityReadingCancelView(CancelRecordView):
    cancel_url_name = "electricity:reading_cancel"

    def get_object(self):
        from django.shortcuts import get_object_or_404
        return get_object_or_404(DailyElectricityReading, pk=self.kwargs["pk"])

    def get_success_url(self):
        return reverse("electricity:reading_list")


def _parse_source_mode(raw) -> str:
    if raw == DailyPowerReading.MODE_WAPDA_SOLAR:
        return DailyPowerReading.MODE_WAPDA_SOLAR
    return DailyPowerReading.MODE_WAPDA


DAILY_POWER_EXPORT_HEADERS = [
    "Date",
    "Source",
    "WAPDA Peak kWh",
    "WAPDA Non-peak kWh",
    "WAPDA Total kWh",
    "Solar kWh",
    "Total kWh",
    "Peak hours",
    "Non-peak hours",
    "Total hours",
    "Remarks",
]


def _daily_power_excel_row(obj: DailyPowerReading) -> list:
    return [
        obj.record_date.isoformat() if obj.record_date else "",
        obj.get_source_mode_display(),
        str(obj.wapda_peak_kwh),
        str(obj.wapda_offpeak_kwh),
        str(obj.wapda_total_kwh),
        str(obj.solar_kwh),
        str(obj.total_kwh),
        str(obj.peak_hours),
        str(obj.offpeak_hours),
        str(obj.total_hours),
        obj.remarks or "",
    ]


class ElectricityHubView(ERPLoginRequiredMixin, TemplateView):
    template_name = "electricity/hub.html"


class DailyPowerListView(ERPLoginRequiredMixin, PaginatedListMixin, ListView):
    model = DailyPowerReading
    template_name = "electricity/daily_list.html"
    context_object_name = "objects"

    def get_queryset(self):
        qs = DailyPowerReading.objects.filter(is_cancelled=False)
        search = self.request.GET.get("q", "")
        qs = apply_search(qs, search, ["remarks", "source_mode"])
        return qs.order_by("-record_date", "-id")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["breadcrumb"] = [
            {"label": "Electricity", "url": reverse("electricity:hub")},
            {"label": "Daily readings"},
        ]
        return ctx


class DailyPowerExportView(ERPLoginRequiredMixin, View):
    def get(self, request):
        return self._export(request)

    def post(self, request):
        return self._export(request)

    def _export(self, request):
        qs = DailyPowerReading.objects.filter(is_cancelled=False).order_by("-record_date", "-id")
        search = (request.POST.get("q") or request.GET.get("q") or "").strip()
        if search:
            qs = apply_search(qs, search, ["remarks", "source_mode"])
        return selective_excel_response(
            request,
            queryset=qs,
            headers=DAILY_POWER_EXPORT_HEADERS,
            row_builder=_daily_power_excel_row,
            filename="electricity_daily_export.xlsx",
            sheet_title="Daily electricity",
            list_redirect="electricity:daily_list",
            today_field="record_date",
        )


class DailyPowerEntryView(ERPLoginRequiredMixin, View):
    template_name = "electricity/daily_form.html"

    def get(self, request):
        return render(request, self.template_name, self._context(request))

    def post(self, request):
        mode = _parse_source_mode(request.POST.get("source_mode"))
        record_date = request.POST.get("record_date") or date.today().isoformat()
        existing = (
            DailyPowerReading.objects.filter(
                record_date=record_date,
                is_cancelled=False,
            ).first()
            if record_date
            else None
        )
        form = DailyPowerReadingForm(request.POST, instance=existing)
        if form.is_valid():
            obj = form.save(commit=False)
            if existing is None:
                obj.created_by = request.user
            obj.updated_by = request.user
            obj.save()
            messages.success(
                request,
                f"Saved electricity reading for {obj.record_date}.",
            )
            return redirect("electricity:daily_list")
        messages.error(request, "Could not save. Check the highlighted fields.")
        return render(
            request,
            self.template_name,
            self._context(request, form=form, mode=mode),
        )

    def _context(self, request, form=None, mode=None):
        today = date.today().isoformat()
        selected_date = (request.GET.get("date") or today).strip() or today
        if mode is None:
            mode = _parse_source_mode(
                request.GET.get("mode") or request.POST.get("source_mode")
            )
        existing = DailyPowerReading.objects.filter(
            record_date=selected_date,
            is_cancelled=False,
        ).first()
        if form is None:
            initial = {
                "record_date": selected_date,
                "source_mode": mode,
                "remarks": existing.remarks if existing else "",
            }
            if existing:
                initial.update(
                    {
                        "source_mode": existing.source_mode if request.method == "GET" and not request.GET.get("mode") else mode,
                        "wapda_peak_kwh": existing.wapda_peak_kwh,
                        "wapda_offpeak_kwh": existing.wapda_offpeak_kwh,
                        "solar_kwh": existing.solar_kwh,
                        "peak_hours": existing.peak_hours,
                        "offpeak_hours": existing.offpeak_hours,
                    }
                )
                if not request.GET.get("mode"):
                    mode = existing.source_mode
            form = DailyPowerReadingForm(instance=existing, initial=initial)
        return {
            "form": form,
            "selected_date": selected_date,
            "selected_mode": mode,
            "includes_solar": mode == DailyPowerReading.MODE_WAPDA_SOLAR,
            "existing": existing,
            "breadcrumb": [
                {"label": "Electricity", "url": reverse("electricity:hub")},
                {"label": "Daily readings", "url": reverse("electricity:daily_list")},
                {"label": "New entry"},
            ],
        }


class DailyPowerDetailView(ERPLoginRequiredMixin, DetailView):
    model = DailyPowerReading
    template_name = "electricity/daily_detail.html"
    context_object_name = "object"

    def get_queryset(self):
        return DailyPowerReading.objects.filter(is_cancelled=False)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["breadcrumb"] = [
            {"label": "Electricity", "url": reverse("electricity:hub")},
            {"label": "Daily readings", "url": reverse("electricity:daily_list")},
            {"label": str(self.object.record_date)},
        ]
        return ctx


class DailyPowerUpdateRedirectView(ERPLoginRequiredMixin, View):
    def get(self, request, pk):
        obj = get_object_or_404(DailyPowerReading, pk=pk, is_cancelled=False)
        return redirect(
            f"{reverse('electricity:daily_entry')}?date={obj.record_date}&mode={obj.source_mode}"
        )


class DailyPowerDeleteView(ERPLoginRequiredMixin, View):
    def post(self, request, pk):
        if not can_soft_delete_records(request.user):
            raise PermissionDenied
        from common.recycle import soft_delete_record

        obj = get_object_or_404(DailyPowerReading, pk=pk)
        label = str(obj.record_date)
        soft_delete_record(obj, request.user)
        messages.success(request, f"Electricity reading {label} moved to Recently Deleted.")
        return redirect("electricity:daily_list")


class DailyPowerMonthlyView(ERPLoginRequiredMixin, TemplateView):
    template_name = "electricity/monthly.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()
        month_start = parse_month_year(
            self.request.GET.get("month"),
            self.request.GET.get("year"),
            today=today,
        )
        report = monthly_power_report(month_start)
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
                    {"label": "Electricity", "url": reverse("electricity:hub")},
                    {"label": "Monthly readings"},
                ],
            }
        )
        return ctx
