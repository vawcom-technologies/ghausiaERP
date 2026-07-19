"""Generic CRUD view factory for master data and transactional models."""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Model
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from accounts.mixins import AuditCreateMixin, AuditUpdateMixin, ERPLoginRequiredMixin, PaginatedListMixin
from accounts.permissions import can_cancel_records, can_edit_completed_lot, is_supervisor
from common.views import apply_search


def make_list_view(model: type[Model], template_name: str, search_fields: list[str], list_fields: list[str]):
    class ListViewImpl(ERPLoginRequiredMixin, PaginatedListMixin, ListView):
        model = model
        template_name = template_name
        context_object_name = "objects"

        def get_queryset(self):
            qs = model.objects.all()
            search = self.request.GET.get("q", "")
            return apply_search(qs, search, search_fields)

        def get_context_data(self, **kwargs):
            ctx = super().get_context_data(**kwargs)
            ctx["search_query"] = self.request.GET.get("q", "")
            ctx["list_fields"] = list_fields
            ctx["model_name"] = model._meta.verbose_name_plural.title()
            return ctx

    return ListViewImpl


def make_create_view(model, form_class, template_name, success_url_name, extra_save=None):
    class CreateViewImpl(ERPLoginRequiredMixin, AuditCreateMixin, CreateView):
        model = model
        form_class = form_class
        template_name = template_name

        def get_form_kwargs(self):
            kwargs = super().get_form_kwargs()
            kwargs["user"] = self.request.user
            for key in ("lot_id", "batch_id", "mixture_id", "job_id"):
                if key in self.request.GET:
                    kwargs[key.replace("_id", "_id")] = self.request.GET.get(key)
            return kwargs

        def get_success_url(self):
            return reverse(success_url_name)

        def form_valid(self, form):
            self.object = form.save(commit=False, user=self.request.user)
            form.instance.created_by = self.request.user
            form.instance.updated_by = self.request.user
            if extra_save:
                extra_save(form, self.request.user)
            else:
                form.save(user=self.request.user)
            messages.success(self.request, f"{model._meta.verbose_name} saved successfully.")
            return super(AuditCreateMixin, self).form_valid(form)

    return CreateViewImpl


def make_update_view(model, form_class, template_name, success_url_name):
    class UpdateViewImpl(ERPLoginRequiredMixin, AuditUpdateMixin, UpdateView):
        model = model
        form_class = form_class
        template_name = template_name

        def dispatch(self, request, *args, **kwargs):
            obj = self.get_object()
            if getattr(obj, "is_cancelled", False):
                messages.error(request, "Cannot edit a cancelled record.")
                return self.response_class(
                    request=request,
                    template=self.template_name,
                    context=self.get_context_data(),
                    using=self.template_engine,
                )
            if hasattr(obj, "status") and obj.status == "Completed":
                if not can_edit_completed_lot(request.user):
                    raise PermissionDenied
            return super().dispatch(request, *args, **kwargs)

        def get_form_kwargs(self):
            kwargs = super().get_form_kwargs()
            kwargs["user"] = self.request.user
            return kwargs

        def get_success_url(self):
            return reverse(success_url_name, kwargs={"pk": self.object.pk})

        def form_valid(self, form):
            form.instance.updated_by = self.request.user
            form.save(user=self.request.user)
            messages.success(self.request, f"{model._meta.verbose_name} updated successfully.")
            return super().form_valid(form)

    return UpdateViewImpl


def make_detail_view(model, template_name, extra_context=None):
    class DetailViewImpl(ERPLoginRequiredMixin, DetailView):
        model = model
        template_name = template_name
        context_object_name = "object"

        def get_context_data(self, **kwargs):
            ctx = super().get_context_data(**kwargs)
            ctx["can_cancel"] = can_cancel_records(self.request.user)
            if extra_context:
                ctx.update(extra_context(self.object))
            return ctx

    return DetailViewImpl
