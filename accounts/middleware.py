"""Block data-entry users from modules they were not assigned."""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin

from accounts.modules import module_for_path
from accounts.permissions import (
    can_access_module,
    can_assign_work,
    can_manage_setup,
    can_permanently_delete,
    can_request_permanent_delete,
    can_view_recycle_bin,
    is_administrator,
)

_OPEN_PREFIXES = (
    "/login/",
    "/logout/",
    "/static/",
    "/media/",
)


class ModuleAccessMiddleware(MiddlewareMixin):
    def process_view(self, request, _view_func, _view_args, _view_kwargs):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return None

        path = request.path

        if path == "/" or path == "/profile/" or any(path.startswith(p) for p in _OPEN_PREFIXES):
            return None

        if path.startswith("/admin/"):
            if not is_administrator(user):
                return _deny(request)
            return None

        if path.startswith("/users/") or path.startswith("/assignments/"):
            if not can_assign_work(user):
                return _deny(request)
            return None

        if path.startswith("/master-data/"):
            if not can_manage_setup(user):
                return _deny(request)
            return None

        if path.startswith("/profile/restore/"):
            if not can_view_recycle_bin(user):
                return _deny(request)
            return None

        if path.startswith("/profile/ask-delete/") or path.startswith("/profile/purge/"):
            if not (can_permanently_delete(user) or can_request_permanent_delete(user)):
                return _deny(request)
            return None

        if path.startswith("/profile/delete-request/"):
            if not can_permanently_delete(user):
                return _deny(request)
            return None

        if path.startswith("/electricity/meters/"):
            from accounts.permissions import is_supervisor
            if not is_supervisor(user):
                return _deny(request)
            return None

        module = module_for_path(path)
        if module and not can_access_module(user, module):
            return _deny(request, "That job is not assigned to you.")
        return None


def _deny(request, message="You do not have access to that page."):
    if request.method in ("GET", "HEAD"):
        messages.warning(request, message)
        return redirect("accounts:home")
    raise PermissionDenied
