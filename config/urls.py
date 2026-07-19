from django.contrib import admin
from django.urls import include, path

import config.admin  # noqa: F401 — register models

admin.site.site_header = "Textile Factory ERP Admin"
admin.site.site_title = "Textile ERP"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("accounts.urls")),
    path("receiving/", include("receiving.urls")),
    path("production/", include("production.urls")),
    path("inventory/", include("inventory.urls")),
    path("maintenance/", include("maintenance.urls")),
    path("electricity/", include("electricity.urls")),
    path("master-data/", include("master_data.urls")),
]
