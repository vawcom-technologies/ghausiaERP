from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from accounts.mixins import AuditCreateMixin, AuditUpdateMixin, CancelRecordView, ERPLoginRequiredMixin, PaginatedListMixin
from common.selective_export import selective_excel_response
from common.views import apply_search
from electricity.forms import DailyElectricityReadingForm, ElectricityMeterForm
from electricity.models import DailyElectricityReading, ElectricityMeter

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


class ElectricityMeterCreateView(ERPLoginRequiredMixin, AuditCreateMixin, CreateView):
    model = ElectricityMeter
    form_class = ElectricityMeterForm
    template_name = "electricity/meter_form.html"
    success_url = reverse_lazy("electricity:meter_list")


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
