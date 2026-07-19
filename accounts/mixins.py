"""Reusable view mixins."""

import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import FormView, ListView, View

from accounts.permissions import can_cancel_records, can_manage_users

logger = logging.getLogger("erp")


class ERPLoginRequiredMixin(LoginRequiredMixin):
    """Require login for all ERP pages."""

    pass


class PaginatedListMixin:
    paginate_by = 25


class AuditCreateMixin:
    """Set created_by and updated_by on create."""

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        return super().form_valid(form)


class AuditUpdateMixin:
    """Set updated_by on update."""

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        return super().form_valid(form)


class CancelRecordView(ERPLoginRequiredMixin, FormView):
    """Generic cancel view requiring a reason."""

    template_name = "includes/cancel_confirm.html"
    cancellation_reason_field = "cancellation_reason"
    success_message = "Record cancelled successfully."

    def dispatch(self, request, *args, **kwargs):
        if not can_cancel_records(request.user):
            raise PermissionDenied
        self.object = self.get_object()
        if self.object.is_cancelled:
            messages.warning(request, "This record is already cancelled.")
            return redirect(self.get_success_url())
        return super().dispatch(request, *args, **kwargs)

    def get_object(self):
        raise NotImplementedError

    def get_success_url(self):
        raise NotImplementedError

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["object"] = self.object
        ctx["object_label"] = str(self.object)
        ctx["cancel_url"] = reverse(self.cancel_url_name, kwargs={"pk": self.object.pk})
        return ctx

    def get_form(self, form_class=None):
        from django import forms

        class CancelForm(forms.Form):
            cancellation_reason = forms.CharField(
                widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
                label="Cancellation Reason",
                required=True,
            )

        return CancelForm(self.request.POST or None)

    @transaction.atomic
    def form_valid(self, form):
        reason = form.cleaned_data["cancellation_reason"]
        self.object.cancel(self.request.user, reason)
        self.on_cancel(reason)
        logger.info("Record cancelled: %s by %s", self.object, self.request.user)
        messages.success(self.request, self.success_message)
        return redirect(self.get_success_url())

    def on_cancel(self, reason: str) -> None:
        """Hook for additional cancellation logic."""
        pass
