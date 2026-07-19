"""Permission helpers for role-based access."""

from functools import wraps

from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied


GROUP_ADMIN = "Administrator"
GROUP_SUPERVISOR = "Supervisor"
GROUP_DATA_ENTRY = "Data Entry User"


def user_in_group(user, group_name: str) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name=group_name).exists()


def is_administrator(user) -> bool:
    return user.is_superuser or user_in_group(user, GROUP_ADMIN)


def is_supervisor(user) -> bool:
    return is_administrator(user) or user_in_group(user, GROUP_SUPERVISOR)


def is_data_entry(user) -> bool:
    return user_in_group(user, GROUP_DATA_ENTRY)


def can_manage_users(user) -> bool:
    return is_administrator(user)


def can_cancel_records(user) -> bool:
    return is_supervisor(user)


def can_override_stock(user) -> bool:
    return is_supervisor(user)


def can_edit_completed_lot(user) -> bool:
    return is_supervisor(user)


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
        if not can_manage_users(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapper
