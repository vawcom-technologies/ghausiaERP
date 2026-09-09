from django.urls import path

from electricity import views

app_name = "electricity"

urlpatterns = [
    path("", views.ElectricityHubView.as_view(), name="hub"),
    path("daily/", views.DailyPowerListView.as_view(), name="daily_list"),
    path("daily/export/", views.DailyPowerExportView.as_view(), name="daily_export"),
    path("daily/new/", views.DailyPowerEntryView.as_view(), name="daily_entry"),
    path("daily/<int:pk>/", views.DailyPowerDetailView.as_view(), name="daily_detail"),
    path("daily/<int:pk>/edit/", views.DailyPowerUpdateRedirectView.as_view(), name="daily_edit"),
    path("daily/<int:pk>/delete/", views.DailyPowerDeleteView.as_view(), name="daily_delete"),
    path("monthly/", views.DailyPowerMonthlyView.as_view(), name="monthly"),
    path("meters/", views.ElectricityMeterListView.as_view(), name="meter_list"),
    path("meters/new/", views.ElectricityMeterCreateView.as_view(), name="meter_create"),
    path("meters/<int:pk>/edit/", views.ElectricityMeterUpdateView.as_view(), name="meter_edit"),
    path("readings/", views.ElectricityReadingListView.as_view(), name="reading_list"),
    path("readings/export/", views.ElectricityReadingExportView.as_view(), name="reading_export"),
    path("readings/new/", views.ElectricityReadingCreateView.as_view(), name="reading_create"),
    path("readings/<int:pk>/", views.ElectricityReadingDetailView.as_view(), name="reading_detail"),
    path("readings/<int:pk>/cancel/", views.ElectricityReadingCancelView.as_view(), name="reading_cancel"),
]
