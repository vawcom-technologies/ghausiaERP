from django.urls import path

from maintenance import views

app_name = "maintenance"

urlpatterns = [
    path("", views.MaintenanceJobListView.as_view(), name="list"),
    path("export/", views.MaintenanceJobExportView.as_view(), name="export"),
    path("new/", views.MaintenanceJobCreateView.as_view(), name="create"),
    path("<int:pk>/", views.MaintenanceJobDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.MaintenanceJobUpdateView.as_view(), name="edit"),
    path("<int:pk>/cancel/", views.MaintenanceJobCancelView.as_view(), name="cancel"),
    path("material/new/", views.MaintenanceMaterialUsageCreateView.as_view(), name="material_create"),
    path("material/<int:pk>/cancel/", views.MaintenanceMaterialUsageCancelView.as_view(), name="material_cancel"),
]
