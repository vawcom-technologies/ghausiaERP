from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView, View

from accounts.mixins import AuditCreateMixin, AuditUpdateMixin, CancelRecordView, ERPLoginRequiredMixin, PaginatedListMixin
from common.views import apply_search
from inventory.models import MaterialTransaction
from inventory.services.stock import reverse_material_transaction
from production.forms import (
    CalenderEntryForm,
    ComfortEntryForm,
    DyeingBatchForm,
    DyeingMaterialUsageForm,
    FinishedStockForm,
    MixtureForm,
    MixtureIngredientForm,
    ProductionLotForm,
    SingeingEntryForm,
    SixChamberEntryForm,
)
from production.models import (
    CalenderEntry,
    ComfortEntry,
    DyeingBatch,
    DyeingMaterialUsage,
    FinishedStock,
    Mixture,
    MixtureIngredient,
    ProductionLot,
    SingeingEntry,
    SixChamberEntry,
)
from production.services.lot import complete_dyeing_stage, get_lot_detail_context


def _form_kwargs(view):
    kwargs = {"user": view.request.user}
    for key in ("lot_id", "batch_id", "mixture_id"):
        if key in view.request.GET:
            kwargs[key] = view.request.GET.get(key)
    return kwargs


# --- Production Lots ---
class ProductionLotListView(ERPLoginRequiredMixin, PaginatedListMixin, ListView):
    model = ProductionLot
    template_name = "production/lot_list.html"
    context_object_name = "objects"

    def get_queryset(self):
        qs = ProductionLot.objects.select_related("vendor", "cloth_type")
        search = self.request.GET.get("q", "")
        qs = apply_search(qs, search, ["lot_number"])
        stage = self.request.GET.get("stage", "")
        status = self.request.GET.get("status", "")
        if stage:
            qs = qs.filter(current_stage=stage)
        if status:
            qs = qs.filter(status=status)
        return qs.order_by("-start_date")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["stage_choices"] = ProductionLot.STAGE_CHOICES
        ctx["status_choices"] = ProductionLot.STATUS_CHOICES
        return ctx


class ProductionLotDetailView(ERPLoginRequiredMixin, DetailView):
    model = ProductionLot
    template_name = "production/lot_detail.html"
    context_object_name = "lot"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(get_lot_detail_context(self.object))
        ctx["can_complete_dyeing"] = (
            self.object.current_stage == "Dyeing"
            and not self.object.dyeing_completed
            and self.object.dyeing_batches.filter(is_cancelled=False).exists()
        )
        return ctx


class CompleteDyeingView(ERPLoginRequiredMixin, View):
    def post(self, request, pk):
        lot = get_object_or_404(ProductionLot, pk=pk)
        complete_dyeing_stage(lot, request.user)
        messages.success(request, "Dyeing stage completed. Lot moved to Six Chamber.")
        return redirect("production:lot_detail", pk=pk)


# --- Singeing ---
class SingeingListView(ERPLoginRequiredMixin, PaginatedListMixin, ListView):
    model = SingeingEntry
    template_name = "production/process_list.html"
    context_object_name = "objects"

    def get_queryset(self):
        return SingeingEntry.objects.select_related("production_lot", "machine").order_by("-process_date")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({"title": "Singeing", "create_url": "production:singeing_create", "detail_url": "production:singeing_detail"})
        return ctx


class SingeingCreateView(ERPLoginRequiredMixin, AuditCreateMixin, CreateView):
    model = SingeingEntry
    form_class = SingeingEntryForm
    template_name = "production/form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(_form_kwargs(self))
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        form.save(user=self.request.user)
        messages.success(self.request, "Singeing entry saved.")
        return redirect("production:singeing_list")


class SingeingDetailView(ERPLoginRequiredMixin, DetailView):
    model = SingeingEntry
    template_name = "production/process_detail.html"


class SingeingCancelView(CancelRecordView):
    cancel_url_name = "production:singeing_cancel"

    def get_object(self):
        return get_object_or_404(SingeingEntry, pk=self.kwargs["pk"])

    def get_success_url(self):
        return reverse("production:singeing_detail", kwargs={"pk": self.object.pk})


# --- Dyeing ---
class DyeingListView(ERPLoginRequiredMixin, PaginatedListMixin, ListView):
    model = DyeingBatch
    template_name = "production/dyeing_list.html"
    context_object_name = "objects"

    def get_queryset(self):
        return DyeingBatch.objects.select_related("production_lot", "jet_machine").order_by("-process_date")


class DyeingCreateView(ERPLoginRequiredMixin, AuditCreateMixin, CreateView):
    model = DyeingBatch
    form_class = DyeingBatchForm
    template_name = "production/form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(_form_kwargs(self))
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        form.save()
        messages.success(self.request, "Dyeing batch saved.")
        return redirect("production:dyeing_list")


class DyeingDetailView(ERPLoginRequiredMixin, DetailView):
    model = DyeingBatch
    template_name = "production/dyeing_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["material_usages"] = self.object.material_usages.filter(is_cancelled=False)
        ctx["mixtures"] = self.object.mixtures.filter(is_cancelled=False)
        return ctx


class DyeingMaterialUsageCreateView(ERPLoginRequiredMixin, AuditCreateMixin, CreateView):
    model = DyeingMaterialUsage
    form_class = DyeingMaterialUsageForm
    template_name = "production/form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(_form_kwargs(self))
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        form.save(user=self.request.user)
        messages.success(self.request, "Material usage recorded.")
        return redirect("production:dyeing_detail", pk=form.instance.dyeing_batch_id)


class DyeingMaterialUsageCancelView(CancelRecordView):
    cancel_url_name = "production:dyeing_material_cancel"

    def get_object(self):
        return get_object_or_404(DyeingMaterialUsage, pk=self.kwargs["pk"])

    def get_success_url(self):
        return reverse("production:dyeing_detail", kwargs={"pk": self.object.dyeing_batch_id})

    def on_cancel(self, reason):
        for tx in MaterialTransaction.objects.filter(dyeing_material_usage=self.object, is_cancelled=False):
            reverse_material_transaction(tx, self.request.user, reason)
            tx.cancel(self.request.user, reason)


# --- Mixture ---
class MixtureCreateView(ERPLoginRequiredMixin, AuditCreateMixin, CreateView):
    model = Mixture
    form_class = MixtureForm
    template_name = "production/form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(_form_kwargs(self))
        if "batch_id" in self.request.GET:
            kwargs.setdefault("initial", {})["dyeing_batch"] = self.request.GET.get("batch_id")
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        form.save()
        messages.success(self.request, "Mixture saved.")
        return redirect("production:mixture_detail", pk=form.instance.pk)


class MixtureDetailView(ERPLoginRequiredMixin, DetailView):
    model = Mixture
    template_name = "production/mixture_detail.html"


class MixtureIngredientCreateView(ERPLoginRequiredMixin, AuditCreateMixin, CreateView):
    model = MixtureIngredient
    form_class = MixtureIngredientForm
    template_name = "production/form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(_form_kwargs(self))
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        form.save(user=self.request.user)
        messages.success(self.request, "Ingredient added.")
        return redirect("production:mixture_detail", pk=form.instance.mixture_id)


# --- Six Chamber ---
class SixChamberListView(ERPLoginRequiredMixin, PaginatedListMixin, ListView):
    model = SixChamberEntry
    template_name = "production/process_list.html"
    context_object_name = "objects"

    def get_queryset(self):
        return SixChamberEntry.objects.select_related("production_lot").order_by("-process_date")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({"title": "Six Chamber", "create_url": "production:sixchamber_create", "detail_url": "production:sixchamber_detail"})
        return ctx


class SixChamberCreateView(ERPLoginRequiredMixin, AuditCreateMixin, CreateView):
    model = SixChamberEntry
    form_class = SixChamberEntryForm
    template_name = "production/form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(_form_kwargs(self))
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        form.save(user=self.request.user)
        messages.success(self.request, "Six Chamber entry saved.")
        return redirect("production:sixchamber_list")


class SixChamberDetailView(ERPLoginRequiredMixin, DetailView):
    model = SixChamberEntry
    template_name = "production/process_detail.html"


# --- Calender ---
class CalenderListView(ERPLoginRequiredMixin, PaginatedListMixin, ListView):
    model = CalenderEntry
    template_name = "production/process_list.html"
    context_object_name = "objects"

    def get_queryset(self):
        return CalenderEntry.objects.select_related("production_lot").order_by("-process_date")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({"title": "Calender", "create_url": "production:calender_create", "detail_url": "production:calender_detail"})
        return ctx


class CalenderCreateView(ERPLoginRequiredMixin, AuditCreateMixin, CreateView):
    model = CalenderEntry
    form_class = CalenderEntryForm
    template_name = "production/form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(_form_kwargs(self))
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        form.save(user=self.request.user)
        messages.success(self.request, "Calender entry saved.")
        return redirect("production:calender_list")


class CalenderDetailView(ERPLoginRequiredMixin, DetailView):
    model = CalenderEntry
    template_name = "production/process_detail.html"


# --- Comfort ---
class ComfortListView(ERPLoginRequiredMixin, PaginatedListMixin, ListView):
    model = ComfortEntry
    template_name = "production/process_list.html"
    context_object_name = "objects"

    def get_queryset(self):
        return ComfortEntry.objects.select_related("production_lot").order_by("-process_date")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({"title": "Comfort", "create_url": "production:comfort_create", "detail_url": "production:comfort_detail"})
        return ctx


class ComfortCreateView(ERPLoginRequiredMixin, AuditCreateMixin, CreateView):
    model = ComfortEntry
    form_class = ComfortEntryForm
    template_name = "production/form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(_form_kwargs(self))
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        form.save(user=self.request.user)
        messages.success(self.request, "Comfort entry saved.")
        return redirect("production:comfort_list")


class ComfortDetailView(ERPLoginRequiredMixin, DetailView):
    model = ComfortEntry
    template_name = "production/process_detail.html"


# --- Finished Stock ---
class FinishedStockListView(ERPLoginRequiredMixin, PaginatedListMixin, ListView):
    model = FinishedStock
    template_name = "production/finished_list.html"
    context_object_name = "objects"

    def get_queryset(self):
        return FinishedStock.objects.select_related("production_lot").order_by("-completion_date")


class FinishedStockCreateView(ERPLoginRequiredMixin, AuditCreateMixin, CreateView):
    model = FinishedStock
    form_class = FinishedStockForm
    template_name = "production/form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(_form_kwargs(self))
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        form.save(user=self.request.user)
        messages.success(self.request, "Finished stock recorded. Production lot completed.")
        return redirect("production:finished_list")


class FinishedStockDetailView(ERPLoginRequiredMixin, DetailView):
    model = FinishedStock
    template_name = "production/finished_detail.html"

    def get_context_data(self, **kwargs):
        from production.services.calculations import calculate_shrinkage

        ctx = super().get_context_data(**kwargs)
        lot = self.object.production_lot
        total_loss, shrinkage = calculate_shrinkage(lot.initial_metres, self.object.final_metres)
        ctx["total_metre_loss"] = total_loss
        ctx["shrinkage_percentage"] = shrinkage
        return ctx
