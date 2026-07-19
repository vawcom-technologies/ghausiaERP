from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from accounts.mixins import AuditCreateMixin, AuditUpdateMixin, CancelRecordView, ERPLoginRequiredMixin, PaginatedListMixin
from common.views import apply_search
from inventory.models import MaterialTransaction
from inventory.services.stock import reverse_material_transaction
from maintenance.forms import MaintenanceJobForm, MaintenanceMaterialUsageForm
from maintenance.models import MaintenanceJob, MaintenanceMaterialUsage
from maintenance.services.maintenance import get_breakdown_duration, get_repair_duration


class MaintenanceJobListView(ERPLoginRequiredMixin, PaginatedListMixin, ListView):
    model = MaintenanceJob
    template_name = "maintenance/list.html"
    context_object_name = "objects"

    def get_queryset(self):
        qs = MaintenanceJob.objects.select_related("machine")
        search = self.request.GET.get("q", "")
        qs = apply_search(qs, search, ["job_number", "fault_description"])
        status = self.request.GET.get("status", "")
        if status:
            qs = qs.filter(status=status)
        return qs.order_by("-reported_datetime")


class MaintenanceJobCreateView(ERPLoginRequiredMixin, AuditCreateMixin, CreateView):
    model = MaintenanceJob
    form_class = MaintenanceJobForm
    template_name = "maintenance/form.html"
    success_url = reverse_lazy("maintenance:list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        form.save(user=self.request.user)
        messages.success(self.request, "Maintenance job created.")
        return redirect(self.success_url)


class MaintenanceJobUpdateView(ERPLoginRequiredMixin, AuditUpdateMixin, UpdateView):
    model = MaintenanceJob
    form_class = MaintenanceJobForm
    template_name = "maintenance/form.html"

    def get_success_url(self):
        return reverse("maintenance:detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        form.save(user=self.request.user)
        messages.success(self.request, "Maintenance job updated.")
        return redirect(self.get_success_url())


class MaintenanceJobDetailView(ERPLoginRequiredMixin, DetailView):
    model = MaintenanceJob
    template_name = "maintenance/detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        usages = self.object.material_usages.filter(is_cancelled=False).select_related("material")
        ctx["oil_used"] = [u for u in usages if u.material.category == "Oil"]
        ctx["grease_used"] = [u for u in usages if u.material.category == "Grease"]
        ctx["spare_items"] = [u for u in usages if u.material.category == "Maintenance Item"]
        ctx["breakdown_duration"] = get_breakdown_duration(self.object)
        ctx["repair_duration"] = get_repair_duration(self.object)
        return ctx


class MaintenanceMaterialUsageCreateView(ERPLoginRequiredMixin, AuditCreateMixin, CreateView):
    model = MaintenanceMaterialUsage
    form_class = MaintenanceMaterialUsageForm
    template_name = "maintenance/material_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        if "job_id" in self.request.GET:
            kwargs["job_id"] = self.request.GET.get("job_id")
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        form.save(user=self.request.user)
        messages.success(self.request, "Maintenance material usage recorded.")
        return redirect("maintenance:detail", pk=form.instance.maintenance_job_id)


class MaintenanceMaterialUsageCancelView(CancelRecordView):
    cancel_url_name = "maintenance:material_cancel"

    def get_object(self):
        return get_object_or_404(MaintenanceMaterialUsage, pk=self.kwargs["pk"])

    def get_success_url(self):
        return reverse("maintenance:detail", kwargs={"pk": self.object.maintenance_job_id})

    def on_cancel(self, reason):
        for tx in MaterialTransaction.objects.filter(
            maintenance_material_usage=self.object, is_cancelled=False
        ):
            reverse_material_transaction(tx, self.request.user, reason)
            tx.cancel(self.request.user, reason)


class MaintenanceJobCancelView(CancelRecordView):
    cancel_url_name = "maintenance:cancel"

    def get_object(self):
        return get_object_or_404(MaintenanceJob, pk=self.kwargs["pk"])

    def get_success_url(self):
        return reverse("maintenance:detail", kwargs={"pk": self.object.pk})
