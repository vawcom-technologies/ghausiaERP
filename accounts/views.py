from urllib.parse import urlparse

from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import TemplateView, View

from accounts.mixins import ERPLoginRequiredMixin
from accounts.modules import MODULE_HOME_LINKS, WORK_MODULES, module_for_path
from accounts.permissions import (
    assigned_modules,
    can_access_module,
    can_permanently_delete,
    can_request_permanent_delete,
    can_restore_deleted,
    can_view_recycle_bin,
    is_data_entry,
    is_supervisor,
)
from electricity.services.electricity import today_power_reading_exists
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
            "electricity_today_entered": today_power_reading_exists(today),
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
        ctx["recently_deleted"] = (
            list_recently_deleted(self.request.user, limit=40)
            if can_view_recycle_bin(self.request.user)
            else []
        )
        if can_permanently_delete(self.request.user):
            from accounts.models import PermanentDeleteRequest

            ctx["pending_delete_requests"] = PermanentDeleteRequest.objects.filter(
                status=PermanentDeleteRequest.STATUS_PENDING
            ).select_related("requested_by")
        else:
            ctx["pending_delete_requests"] = []
        return ctx


class RestoreDeletedView(ERPLoginRequiredMixin, View):
    """Restore a soft-deleted record from the profile recycle bin."""

    def post(self, request, model_key, pk):
        if not can_restore_deleted(request.user):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        from common.recycle import get_deleted_object, get_registry_row, restore_record
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
        if is_data_entry(request.user):
            row = get_registry_row(model_key)
            if row is None or row[4] not in assigned_modules(request.user):
                from django.core.exceptions import PermissionDenied
                raise PermissionDenied

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


class RequestPermanentDeleteView(ERPLoginRequiredMixin, View):
    """Supervisor asks an administrator to wipe a recycled record."""

    def post(self, request, model_key, pk):
        from django.core.exceptions import PermissionDenied

        from common.recycle import request_permanent_delete

        if can_permanently_delete(request.user):
            return PurgeDeletedView.as_view()(request, model_key=model_key, pk=pk)
        if not can_request_permanent_delete(request.user):
            raise PermissionDenied
        req = request_permanent_delete(request.user, model_key, pk)
        if req is None:
            messages.error(request, "Deleted record not found or already restored.")
        else:
            messages.success(
                request,
                f"Asked an administrator to permanently delete {req.label}.",
            )
        return redirect("accounts:profile")


class PurgeDeletedView(ERPLoginRequiredMixin, View):
    """Administrator permanently removes a recycled record."""

    def post(self, request, model_key, pk):
        from django.core.exceptions import PermissionDenied

        from accounts.models import PermanentDeleteRequest
        from common.recycle import purge_deleted_object

        if not can_permanently_delete(request.user):
            if can_request_permanent_delete(request.user):
                return RequestPermanentDeleteView.as_view()(request, model_key=model_key, pk=pk)
            raise PermissionDenied
        try:
            label = purge_deleted_object(model_key, pk)
        except Exception as exc:  # noqa: BLE001
            messages.error(request, f"Could not permanently delete that record: {exc}")
            return redirect("accounts:profile")
        if label is None:
            messages.error(request, "Deleted record not found or already restored.")
            return redirect("accounts:profile")
        PermanentDeleteRequest.objects.filter(
            model_key=model_key,
            object_pk=pk,
            status=PermanentDeleteRequest.STATUS_PENDING,
        ).update(
            status=PermanentDeleteRequest.STATUS_APPROVED,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )
        messages.success(request, f"Permanently deleted {label}.")
        return redirect("accounts:profile")


class ReviewPermanentDeleteView(ERPLoginRequiredMixin, View):
    """Admin approves or rejects a supervisor's permanent-delete request."""

    def post(self, request, pk):
        from django.core.exceptions import PermissionDenied

        from accounts.models import PermanentDeleteRequest
        from common.recycle import purge_deleted_object

        if not can_permanently_delete(request.user):
            raise PermissionDenied
        req = get_object_or_404(
            PermanentDeleteRequest,
            pk=pk,
            status=PermanentDeleteRequest.STATUS_PENDING,
        )
        decision = (request.POST.get("decision") or "").strip()
        if decision == "reject":
            req.status = PermanentDeleteRequest.STATUS_REJECTED
            req.reviewed_by = request.user
            req.reviewed_at = timezone.now()
            req.review_note = request.POST.get("note") or "Rejected by administrator."
            req.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note"])
            messages.success(request, f"Kept {req.label} in Recently Deleted.")
            return redirect("accounts:profile")

        try:
            label = purge_deleted_object(req.model_key, req.object_pk)
        except Exception as exc:  # noqa: BLE001
            messages.error(request, f"Could not permanently delete that record: {exc}")
            return redirect("accounts:profile")
        req.status = PermanentDeleteRequest.STATUS_APPROVED
        req.reviewed_by = request.user
        req.reviewed_at = timezone.now()
        req.save(update_fields=["status", "reviewed_by", "reviewed_at"])
        messages.success(request, f"Permanently deleted {label or req.label}.")
        return redirect("accounts:profile")


