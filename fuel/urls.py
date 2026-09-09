from django.urls import path

from fuel import views

app_name = "fuel"

urlpatterns = [
    path("", views.FuelHubView.as_view(), name="hub"),
    path("steam-boiler/", views.SteamBoilerListView.as_view(), name="steam_boiler"),
    path(
        "steam-boiler/monthly/",
        views.SteamBoilerMonthlyView.as_view(),
        name="steam_boiler_monthly",
    ),
    path("steam-boiler/entry/", views.SteamBoilerEntryView.as_view(), name="steam_boiler_entry"),
    path(
        "steam-boiler/<int:pk>/",
        views.SteamBoilerDetailView.as_view(),
        name="steam_boiler_detail",
    ),
    path(
        "steam-boiler/<int:pk>/edit/",
        views.SteamBoilerUpdateRedirectView.as_view(),
        name="steam_boiler_edit",
    ),
    path(
        "steam-boiler/<int:pk>/delete/",
        views.SteamBoilerDeleteView.as_view(),
        name="steam_boiler_delete",
    ),
    path("oil-boiler/", views.OilBoilerListView.as_view(), name="oil_boiler"),
    path(
        "oil-boiler/monthly/",
        views.OilBoilerMonthlyView.as_view(),
        name="oil_boiler_monthly",
    ),
    path("oil-boiler/entry/", views.OilBoilerEntryView.as_view(), name="oil_boiler_entry"),
    path(
        "oil-boiler/<int:pk>/",
        views.OilBoilerDetailView.as_view(),
        name="oil_boiler_detail",
    ),
    path(
        "oil-boiler/<int:pk>/edit/",
        views.OilBoilerUpdateRedirectView.as_view(),
        name="oil_boiler_edit",
    ),
    path(
        "oil-boiler/<int:pk>/delete/",
        views.OilBoilerDeleteView.as_view(),
        name="oil_boiler_delete",
    ),
]
