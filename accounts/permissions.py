"""Permission helpers for role-based access."""

from functools import wraps

from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied

from accounts.modules import MODULE_KEYS

GROUP_ADMIN = "Administrator"
GROUP_SUPERVISOR = "Supervisor"
GROUP_DATA_ENTRY = "Data Entry User"


def ensure_role_groups() -> dict[str, Group]:
    groups = {}
    for name in (GROUP_ADMIN, GROUP_SUPERVISOR, GROUP_DATA_ENTRY):
        groups[name], _ = Group.objects.get_or_create(name=name)
    return groups


def user_in_group(user, group_name: str) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name=group_name).exists()


def is_administrator(user) -> bool:
    return bool(user.is_authenticated and (user.is_superuser or user.groups.filter(name=GROUP_ADMIN).exists()))


def is_supervisor_role(user) -> bool:
    """True only for the Supervisor group (not administrators)."""
    if not user.is_authenticated or is_administrator(user):
        return False
    return user.groups.filter(name=GROUP_SUPERVISOR).exists()


def is_supervisor(user) -> bool:
    """Supervisor or administrator — used for operational overrides."""
    return is_administrator(user) or is_supervisor_role(user)


def is_data_entry(user) -> bool:
    if not user.is_authenticated or is_administrator(user) or is_supervisor_role(user):
        return False
    return user.groups.filter(name=GROUP_DATA_ENTRY).exists()


def can_manage_users(user) -> bool:
    """Admin and supervisor can create/manage data-entry staff."""
    return is_supervisor(user)


def can_assign_work(user) -> bool:
    return is_supervisor(user)


def can_delete_records(user) -> bool:
    return is_administrator(user)


def can_cancel_records(user) -> bool:
    return is_supervisor(user)


def can_override_stock(user) -> bool:
    return is_supervisor(user)


def can_edit_completed_lot(user) -> bool:
    return is_supervisor(user)


def can_manage_setup(user) -> bool:
    return is_supervisor(user)


def assigned_modules(user) -> set[str]:
    if not user.is_authenticated:
        return set()
    if is_supervisor(user):
        return set(MODULE_KEYS)
    from accounts.models import WorkAssignment

    return set(WorkAssignment.objects.filter(user=user).values_list("module", flat=True))


def can_access_module(user, module: str) -> bool:
    if is_supervisor(user):
        return True
    return module in assigned_modules(user)


def role_label(user) -> str:
    if not user.is_authenticated:
        return "Guest"
    if is_administrator(user):
        return GROUP_ADMIN
    if is_supervisor_role(user):
        return GROUP_SUPERVISOR
    if is_data_entry(user):
        return GROUP_DATA_ENTRY
    if user.is_superuser:
        return GROUP_ADMIN
    return "User"


def require_supervisor(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not can_cancel_records(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapper


def require_admin(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not is_administrator(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapper
