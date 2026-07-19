from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from accounts.mixins import AuditCreateMixin, AuditUpdateMixin, CancelRecordView, ERPLoginRequiredMixin, PaginatedListMixin
from common.views import apply_search
from electricity.forms import DailyElectricityReadingForm, ElectricityMeterForm
from electricity.models import DailyElectricityReading, ElectricityMeter


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
