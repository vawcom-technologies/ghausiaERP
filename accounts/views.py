from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import TemplateView, View

from accounts.mixins import ERPLoginRequiredMixin
from accounts.permissions import can_manage_users, require_admin
from electricity.models import DailyElectricityReading, ElectricityMeter
from electricity.services.electricity import active_meters_count, today_readings_count
from inventory.services.stock import get_materials_below_minimum
from maintenance.models import MaintenanceJob
from master_data.models import Machine
from production.models import ProductionLot

User = get_user_model()


class HomeView(ERPLoginRequiredMixin, TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.now().date()
        active_lots = ProductionLot.objects.filter(
            is_cancelled=False, status__in=["Received", "In Production", "On Hold"]
        ).count()
        waiting_dyeing = ProductionLot.objects.filter(
            is_cancelled=False, current_stage="Dyeing"
        ).count()
        open_maintenance = MaintenanceJob.objects.filter(
            is_cancelled=False, status__in=["Reported", "In Progress"]
        ).count()
        broken_machines = Machine.objects.filter(status="Broken Down", is_active=True).count()
        low_stock = get_materials_below_minimum()
        meters = active_meters_count()
        today_readings = today_readings_count()
        ctx.update({
            "active_lots": active_lots,
            "waiting_dyeing": waiting_dyeing,
            "open_maintenance": open_maintenance,
            "broken_machines": broken_machines,
            "low_stock_count": len(low_stock),
            "low_stock_items": low_stock[:10],
            "electricity_today_entered": today_readings >= meters if meters > 0 else today_readings > 0,
            "today_readings": today_readings,
            "active_meters": meters,
            "stage_counts": ProductionLot.objects.filter(is_cancelled=False)
            .values("current_stage")
            .annotate(count=Count("id")),
        })
        return ctx


class ProfileView(ERPLoginRequiredMixin, TemplateView):
    template_name = "accounts/profile.html"

    def get_context_data(self, **kwargs):
        from common.recycle import list_recently_deleted

        ctx = super().get_context_data(**kwargs)
        ctx["profile_user"] = self.request.user
        ctx["recently_deleted"] = list_recently_deleted(limit=40)
        return ctx


class RestoreDeletedView(ERPLoginRequiredMixin, View):
    """Restore a soft-deleted record from the profile recycle bin."""

    def post(self, request, model_key, pk):
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


class UserListView(ERPLoginRequiredMixin, TemplateView):
    template_name = "accounts/user_list.html"

    def dispatch(self, request, *args, **kwargs):
        if not can_manage_users(request.user):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["users"] = User.objects.all().order_by("username")
        ctx["groups"] = Group.objects.all()
        return ctx
