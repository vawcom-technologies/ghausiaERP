from django.urls import path

from attendance import views

app_name = "attendance"

urlpatterns = [
    path("", views.AttendanceHubView.as_view(), name="hub"),
    path(
        "<slug:dept_slug>/export/",
        views.AttendanceExportView.as_view(),
        name="export_department",
    ),
    path(
        "<slug:dept_slug>/<slug:section_slug>/export/",
        views.AttendanceExportView.as_view(),
        name="export_section",
    ),
    path("<slug:dept_slug>/", views.AttendanceDepartmentView.as_view(), name="department"),
    path(
        "<slug:dept_slug>/<slug:section_slug>/",
        views.AttendanceSectionView.as_view(),
        name="section",
    ),
]
