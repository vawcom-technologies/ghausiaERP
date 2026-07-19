from django.urls import path

from electricity import views

app_name = "electricity"

urlpatterns = [
    path("meters/", views.ElectricityMeterListView.as_view(), name="meter_list"),
    path("meters/new/", views.ElectricityMeterCreateView.as_view(), name="meter_create"),
    path("readings/", views.ElectricityReadingListView.as_view(), name="reading_list"),
    path("readings/new/", views.ElectricityReadingCreateView.as_view(), name="reading_create"),
    path("readings/<int:pk>/", views.ElectricityReadingDetailView.as_view(), name="reading_detail"),
    path("readings/<int:pk>/cancel/", views.ElectricityReadingCancelView.as_view(), name="reading_cancel"),
]
