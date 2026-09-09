from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from accounts.mixins import ERPLoginRequiredMixin
from attendance.models import AttendanceRow
from attendance.services import (
    ATTENDANCE_EXPORT_HEADERS,
    attendance_to_excel_row,
    load_register_rows,
    parse_register_post,
    save_register_rows,
    sheet_display_rows,
)
from attendance.structure import DEPARTMENTS, get_department, get_section
from common.excel import build_data_export_response
from common.selective_export import filter_queryset_by_ids, ordered_by_ids, parse_selected_ids

BLANK_ROWS = 15
DAY_RANGE = range(1, 16)


def _register_context(ctx, department, section=None, sheet_rows=None, **extra):
    dept_slug = department["slug"]
    section_slug = section["slug"] if section else ""
    if sheet_rows is None:
        saved = load_register_rows(dept_slug, section_slug)
        sheet_rows = sheet_display_rows(saved, min_rows=BLANK_ROWS)
    ctx["blank_rows"] = range(1, BLANK_ROWS + 1)
    ctx["day_range"] = DAY_RANGE
    ctx["department"] = department
    ctx["section"] = section
    ctx["sheet_rows"] = sheet_rows
    ctx["section_slug"] = section_slug
    ctx.update(extra)
    return ctx


class AttendanceHubView(ERPLoginRequiredMixin, TemplateView):
    template_name = "attendance/hub.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["departments"] = DEPARTMENTS
        return ctx


class AttendanceDepartmentView(ERPLoginRequiredMixin, View):
    """Department hub (sections) or leaf register when the dept has no sections."""

    def get(self, request, dept_slug):
        dept = get_department(dept_slug)
        if dept is None:
            raise Http404("Department not found")
        if dept["sections"]:
            return render(
                request,
                "attendance/department.html",
                {"department": dept},
            )
        ctx = _register_context(
            {},
            dept,
            register_title=dept["name"],
            register_subtitle=dept["description"],
            breadcrumb=[
                {"label": "Attendance", "url": reverse("attendance:hub")},
                {"label": dept["name"]},
            ],
        )
        return render(request, "attendance/register.html", ctx)

    def post(self, request, dept_slug):
        dept = get_department(dept_slug)
        if dept is None:
            raise Http404("Department not found")
        if dept["sections"]:
            return redirect("attendance:department", dept_slug=dept_slug)
        rows = parse_register_post(request.POST)
        saved, _ = save_register_rows(dept_slug, "", rows, request.user)
        messages.success(request, f"Saved {saved} attendance row(s) to the database.")
        return redirect("attendance:department", dept_slug=dept_slug)


class AttendanceSectionView(ERPLoginRequiredMixin, View):
    def get(self, request, dept_slug, section_slug):
        dept, section = get_section(dept_slug, section_slug)
        if dept is None or section is None:
            raise Http404("Section not found")
        ctx = _register_context(
            {},
            dept,
            section,
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
        return render(request, "attendance/register.html", ctx)

    def post(self, request, dept_slug, section_slug):
        dept, section = get_section(dept_slug, section_slug)
        if dept is None or section is None:
            raise Http404("Section not found")
        rows = parse_register_post(request.POST)
        saved, _ = save_register_rows(dept_slug, section_slug, rows, request.user)
        messages.success(request, f"Saved {saved} attendance row(s) to the database.")
        return redirect(
            "attendance:section",
            dept_slug=dept_slug,
            section_slug=section_slug,
        )


class AttendanceExportView(ERPLoginRequiredMixin, View):
    """Export attendance rows for a department/section (supports selected ids)."""

    def get(self, request, dept_slug, section_slug=""):
        return self._export(request, dept_slug, section_slug)

    def post(self, request, dept_slug, section_slug=""):
        return self._export(request, dept_slug, section_slug)

    def _export(self, request, dept_slug, section_slug):
        dept = get_department(dept_slug)
        if dept is None:
            raise Http404("Department not found")
        section_slug = section_slug or ""
        if section_slug:
            dept, section = get_section(dept_slug, section_slug)
            if dept is None or section is None:
                raise Http404("Section not found")
            redirect_name = "attendance:section"
            redirect_kwargs = {"dept_slug": dept_slug, "section_slug": section_slug}
        else:
            if dept["sections"]:
                raise Http404("Section required")
            redirect_name = "attendance:department"
            redirect_kwargs = {"dept_slug": dept_slug}

        ids = parse_selected_ids(request)
        if ids is not None and len(ids) == 0:
            messages.error(request, "Select at least one row to export.")
            return redirect(redirect_name, **redirect_kwargs)

        qs = AttendanceRow.objects.filter(
            department_slug=dept_slug,
            section_slug=section_slug,
        ).order_by("row_number", "id")
        qs = filter_queryset_by_ids(qs, ids)
        objects = ordered_by_ids(qs, ids) if ids is not None else list(qs)

        label = f"{dept_slug}_{section_slug}" if section_slug else dept_slug
        return build_data_export_response(
            filename=f"attendance_{label}_export.xlsx",
            headers=ATTENDANCE_EXPORT_HEADERS,
            rows=[attendance_to_excel_row(obj) for obj in objects],
            sheet_title="Attendance",
        )
