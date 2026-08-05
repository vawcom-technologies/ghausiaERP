from django.urls import path

from gate_entry import views

app_name = "gate_entry"

urlpatterns = [
    path("", views.GateEntryListView.as_view(), name="list"),
    path("sheet/", views.GateEntrySheetView.as_view(), name="sheet"),
    path("<int:pk>/", views.GateEntryDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.GateEntryUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.GateEntryDeleteView.as_view(), name="delete"),
    # Alias used by earlier placeholder nav
    path("entry/", views.GateEntrySheetView.as_view(), name="home"),
]
