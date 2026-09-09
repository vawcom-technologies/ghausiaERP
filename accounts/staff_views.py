"""User creation and work-assignment views for admin and supervisor."""

from django.contrib import messages
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import TemplateView, View

from accounts.forms import StaffUserCreateForm
from accounts.job_accounts import JOB_STATION_ACCOUNTS, ensure_job_station_accounts
from accounts.mixins import ERPLoginRequiredMixin
from accounts.models import WorkAssignment
from accounts.modules import MODULE_KEYS, MODULE_LABELS, WORK_MODULES, grouped_work_modules
from accounts.permissions import (
    GROUP_ADMIN,
    GROUP_DATA_ENTRY,
    GROUP_SUPERVISOR,
    can_assign_work,
    ensure_role_groups,
    is_administrator,
    is_data_entry,
    is_supervisor_role,
    role_label,
)


class StaffRequiredMixin(ERPLoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not can_assign_work(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


def _data_entry_queryset():
    return (
        User.objects.filter(groups__name=GROUP_DATA_ENTRY, is_superuser=False)
        .exclude(groups__name__in=[GROUP_ADMIN, GROUP_SUPERVISOR])
        .distinct()
        .order_by("first_name", "username")
    )


def _user_rows(users):
    assigned = {}
    for row in WorkAssignment.objects.filter(user__in=users).values_list("user_id", "module"):
        assigned.setdefault(row[0], set()).add(row[1])
    rows = []
    for user in users:
        modules = assigned.get(user.pk, set())
        rows.append(
            {
                "user": user,
                "role": role_label(user),
                "modules": modules,
                "module_labels": [MODULE_LABELS[key] for key in MODULE_KEYS if key in modules],
            }
        )
    return rows


class UserListView(StaffRequiredMixin, TemplateView):
    template_name = "accounts/user_list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        users = User.objects.prefetch_related("groups").order_by("username")
        if not is_administrator(self.request.user):
            users = users.exclude(is_superuser=True).exclude(groups__name=GROUP_ADMIN)
        ctx["user_rows"] = _user_rows(users)
        ctx["job_logins"] = [
            {
                "username": username,
                "password": password,
                "name": f"{first} {last}".strip(),
                "job": MODULE_LABELS.get(module, module),
            }
            for username, password, first, last, module in JOB_STATION_ACCOUNTS
        ]
        return ctx


class StaffUserCreateView(StaffRequiredMixin, View):
    template_name = "accounts/user_form.html"

    def get(self, request):
        return render(request, self.template_name, {"form": StaffUserCreateForm(creator=request.user)})

    def post(self, request):
        form = StaffUserCreateForm(request.POST, creator=request.user)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        groups = ensure_role_groups()
        role = form.cleaned_data["role"]
        with transaction.atomic():
            user = User.objects.create_user(
                username=form.cleaned_data["username"],
                password=form.cleaned_data["password1"],
                first_name=form.cleaned_data.get("first_name") or "",
                last_name=form.cleaned_data.get("last_name") or "",
            )
            user.is_staff = role == GROUP_ADMIN
            user.save(update_fields=["is_staff"])
            user.groups.set([groups[role]])
            if role == GROUP_DATA_ENTRY:
                _replace_assignments(user, form.cleaned_data.get("modules") or [], request.user)

        messages.success(request, f"Created {role_label(user)} account for {user.username}.")
        return redirect("accounts:assignments")


class AssignmentDashboardView(StaffRequiredMixin, View):
    template_name = "accounts/assignments.html"

    def get(self, request):
        users = list(_data_entry_queryset().prefetch_related("groups", "work_assignments"))
        return render(
            request,
            self.template_name,
            {
                "rows": _user_rows(users),
                "work_modules": WORK_MODULES,
                "work_module_groups": grouped_work_modules(),
            },
        )

    def post(self, request):
        users = list(_data_entry_queryset())
        with transaction.atomic():
            for user in users:
                selected = [key for key in request.POST.getlist(f"modules_{user.pk}") if key in MODULE_KEYS]
                _replace_assignments(user, selected, request.user)
        messages.success(request, "Work assignments updated.")
        return redirect("accounts:assignments")


class ToggleUserActiveView(StaffRequiredMixin, View):
    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        if user.pk == request.user.pk:
            messages.error(request, "You cannot deactivate your own account.")
            return redirect("accounts:users")
        if is_administrator(user) and not is_administrator(request.user):
            raise PermissionDenied
        if is_supervisor_role(user) and not is_administrator(request.user):
            raise PermissionDenied
        if not is_administrator(request.user) and not is_data_entry(user):
            raise PermissionDenied
        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])
        state = "activated" if user.is_active else "deactivated"
        messages.success(request, f"{user.username} {state}.")
        return redirect("accounts:users")


class CreateJobAccountsView(StaffRequiredMixin, View):
    """Create one data-entry login per factory job, each locked to that job only."""

    def post(self, request):
        created, _updated = ensure_job_station_accounts(assigned_by=request.user)
        if created:
            names = ", ".join(row["username"] for row in created)
            messages.success(request, f"Created job accounts: {names}. Default passwords are listed on this page.")
        else:
            messages.success(request, "Job accounts are already in place. Each one is locked to a single job.")
        return redirect("accounts:users")


def _replace_assignments(user, module_keys, assigned_by):
    WorkAssignment.objects.filter(user=user).exclude(module__in=module_keys).delete()
    existing = set(WorkAssignment.objects.filter(user=user).values_list("module", flat=True))
    for key in module_keys:
        if key not in existing:
            WorkAssignment.objects.create(user=user, module=key, assigned_by=assigned_by)
