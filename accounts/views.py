from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
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
