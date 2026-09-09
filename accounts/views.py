from urllib.parse import urlparse

from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.db.models import Count
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import TemplateView, View

from accounts.mixins import ERPLoginRequiredMixin
from accounts.modules import MODULE_HOME_LINKS, WORK_MODULES, module_for_path
from accounts.permissions import (
    assigned_modules,
    can_access_module,
    can_delete_records,
    is_data_entry,
    is_supervisor,
)
from electricity.services.electricity import active_meters_count, today_readings_count
from gate_entry.models import GateEntry
from inventory.services.stock import get_materials_below_minimum
from maintenance.models import MaintenanceJob
from master_data.models import Machine
from production.models import ProductionLot
from receiving.models import ClothReceipt


class ERPLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        raw = self.get_redirect_url()
        if not raw:
            return reverse("accounts:home")
        path = urlparse(raw).path or "/"
        user = self.request.user
        if path in ("/", "/profile/"):
            return raw
        module = module_for_path(path)
        if module and can_access_module(user, module):
            return raw
        if is_data_entry(user):
            return reverse("accounts:home")
        if path.startswith("/users/") or path.startswith("/master-data/") or path.startswith("/admin/"):
            if is_data_entry(user):
                return reverse("accounts:home")
        return raw


class HomeView(ERPLoginRequiredMixin, TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.localdate()
        active_lot_qs = ProductionLot.objects.filter(
            is_cancelled=False, status__in=["Received", "In Production", "On Hold"]
        )
        stage_map = {
            row["current_stage"]: row["count"]
            for row in active_lot_qs.values("current_stage").annotate(count=Count("id"))
        }
        low_stock = get_materials_below_minimum() if is_supervisor(user) else []
        meters = active_meters_count()
        today_readings = today_readings_count()
        assigned = assigned_modules(user)
        ctx.update({
            "active_lots": active_lot_qs.count(),
            "lots_on_hold": active_lot_qs.filter(status="On Hold").count(),
            "waiting_dyeing": active_lot_qs.filter(current_stage="Dyeing").count(),
            "open_maintenance": MaintenanceJob.objects.filter(
                is_cancelled=False, status__in=["Reported", "In Progress"]
            ).count(),
            "broken_machines": Machine.objects.filter(status="Broken Down", is_active=True).count(),
            "low_stock_count": len(low_stock),
            "low_stock_items": low_stock[:10],
            "electricity_today_entered": today_readings >= meters if meters > 0 else today_readings > 0,
            "today_readings": today_readings,
            "active_meters": meters,
            "today_gate_entries": GateEntry.objects.filter(
                is_cancelled=False, entry_date=today
            ).count(),
            "today_receipts": ClothReceipt.objects.filter(
                is_cancelled=False, receipt_date=today
            ).count(),
            "stage_pipeline": [
                {"stage": stage, "count": stage_map.get(stage, 0)}
                for stage, _label in ProductionLot.STAGE_CHOICES
                if stage != "Finished"
            ],
            "show_ops_dashboard": is_supervisor(user),
            "assigned_job_cards": [
                {
                    "key": key,
                    "label": label,
                    "icon": icon,
                    "url_name": MODULE_HOME_LINKS[key][0],
                    "description": MODULE_HOME_LINKS[key][1],
                }
                for key, label, icon in WORK_MODULES
                if is_data_entry(user) and key in assigned
            ],
        })
        return ctx


class ProfileView(ERPLoginRequiredMixin, TemplateView):
    template_name = "accounts/profile.html"

    def get_context_data(self, **kwargs):
        from common.recycle import list_recently_deleted

        ctx = super().get_context_data(**kwargs)
        ctx["profile_user"] = self.request.user
        ctx["recently_deleted"] = list_recently_deleted(limit=40) if can_delete_records(self.request.user) else []
        return ctx


class RestoreDeletedView(ERPLoginRequiredMixin, View):
    """Restore a soft-deleted record from the profile recycle bin."""

    def post(self, request, model_key, pk):
        if not can_delete_records(request.user):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        from common.recycle import get_deleted_object, restore_record
        from production.models import (
            CalenderEntry,
            ComfortEntry,
            DyeingBatch,
            DyeingMaterialUsage,
            FinishedStock,
            Mixture,
            MixtureIngredient,
            ProcessMaterialUsage,
            ProductionLot,
            SingeingEntry,
            SixChamberEntry,
        )

        obj = get_deleted_object(model_key, pk)
        if obj is None:
            messages.error(request, "Deleted record not found or already restored.")
            return redirect("accounts:profile")

        label = str(obj)
        try:
            with transaction.atomic():
                if model_key == "cloth_receipt":
                    lot = (
                        ProductionLot.all_objects.filter(cloth_receipt_id=obj.pk, is_deleted=True)
                        .order_by("-deleted_at")
                        .first()
                    )
                    if lot is not None:
                        # Restore production children first, then lot, then receipt
                        for batch in DyeingBatch.all_objects.filter(
                            production_lot=lot, is_deleted=True
                        ):
                            for usage in DyeingMaterialUsage.all_objects.filter(
                                dyeing_batch=batch, is_deleted=True
                            ):
                                restore_record(usage, request.user)
                            for mixture in Mixture.all_objects.filter(
                                dyeing_batch=batch, is_deleted=True
                            ):
                                for ingredient in MixtureIngredient.all_objects.filter(
                                    mixture=mixture, is_deleted=True
                                ):
                                    restore_record(ingredient, request.user)
                                restore_record(mixture, request.user)
                            restore_record(batch, request.user)

                        for model in (
                            SingeingEntry,
                            SixChamberEntry,
                            CalenderEntry,
                            ComfortEntry,
                            FinishedStock,
                            ProcessMaterialUsage,
                        ):
                            for child in model.all_objects.filter(
                                production_lot=lot, is_deleted=True
                            ):
                                restore_record(child, request.user)

                        restore_record(lot, request.user)
                restore_record(obj, request.user)
        except Exception as exc:  # noqa: BLE001
            messages.error(request, f"Could not restore {label}: {exc}")
            return redirect("accounts:profile")

        messages.success(request, f"Restored {label}.")
        return redirect("accounts:profile")


