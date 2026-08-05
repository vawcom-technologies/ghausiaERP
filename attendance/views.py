from django.http import Http404
from django.urls import reverse
from django.views.generic import TemplateView

from accounts.mixins import ERPLoginRequiredMixin
from attendance.structure import DEPARTMENTS, get_department, get_section

BLANK_ROWS = range(1, 16)
DAY_RANGE = range(1, 16)


def _register_context(ctx, **extra):
    ctx["blank_rows"] = BLANK_ROWS
    ctx["day_range"] = DAY_RANGE
    ctx.update(extra)
    return ctx


class AttendanceHubView(ERPLoginRequiredMixin, TemplateView):
    template_name = "attendance/hub.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["departments"] = DEPARTMENTS
        return ctx


class AttendanceDepartmentView(ERPLoginRequiredMixin, TemplateView):
    """Department hub (sections) or leaf register when the dept has no sections."""

    def get_template_names(self):
        dept = get_department(self.kwargs["dept_slug"])
        if dept is None:
            raise Http404("Department not found")
        if dept["sections"]:
            return ["attendance/department.html"]
        return ["attendance/register.html"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        dept = get_department(self.kwargs["dept_slug"])
        if dept is None:
            raise Http404("Department not found")
        ctx["department"] = dept
        if not dept["sections"]:
            _register_context(
                ctx,
                register_title=dept["name"],
                register_subtitle=dept["description"],
                breadcrumb=[
                    {"label": "Attendance", "url": reverse("attendance:hub")},
                    {"label": dept["name"]},
                ],
            )
        return ctx


class AttendanceSectionView(ERPLoginRequiredMixin, TemplateView):
    template_name = "attendance/register.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        dept, section = get_section(self.kwargs["dept_slug"], self.kwargs["section_slug"])
        if dept is None or section is None:
            raise Http404("Section not found")
        return _register_context(
            ctx,
            department=dept,
            section=section,
            register_title=f"{dept['name']} — {section['name']}",
            register_subtitle=section["description"],
            breadcrumb=[
                {"label": "Attendance", "url": reverse("attendance:hub")},
                {
                    "label": dept["name"],
                    "url": reverse("attendance:department", kwargs={"dept_slug": dept["slug"]}),
                },
                {"label": section["name"]},
            ],
        )
