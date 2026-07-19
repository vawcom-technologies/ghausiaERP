from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

import config.admin  # noqa: F401 — register models

admin.site.site_header = "Ghausia Dyeing Admin"
admin.site.site_title = "Ghausia Dyeing"

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

# Serve uploaded receipt photos in local/dev deployments.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
