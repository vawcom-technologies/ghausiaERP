from django.urls import path

from gate_entry import views

app_name = "gate_entry"

urlpatterns = [
    path("", views.GateEntryListView.as_view(), name="list"),
    path("sheet/", views.GateEntrySheetView.as_view(), name="sheet"),
    # Alias used by earlier placeholder nav
    path("entry/", views.GateEntrySheetView.as_view(), name="home"),
]
