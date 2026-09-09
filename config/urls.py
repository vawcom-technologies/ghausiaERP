from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.urls import include, path
from django.views.static import serve

import config.admin  # noqa: F401 — register models

admin.site.site_header = "Ghausia Dyeing Admin"
admin.site.site_title = "Ghausia Dyeing"

handler403 = "django.views.defaults.permission_denied"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("accounts.urls")),
    path("gate-entry/", include("gate_entry.urls")),
    path("receiving/", include("receiving.urls")),
    path("production/", include("production.urls")),
    path("inventory/", include("inventory.urls")),
    path("maintenance/", include("maintenance.urls")),
    path("electricity/", include("electricity.urls")),
    path("attendance/", include("attendance.urls")),
    path("fuel/", include("fuel.urls")),
    path("master-data/", include("master_data.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    urlpatterns += [
        path(
            "media/<path:path>",
            login_required(serve),
            {"document_root": settings.MEDIA_ROOT},
        ),
    ]
