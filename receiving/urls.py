from django.urls import path

from receiving import views

app_name = "receiving"

urlpatterns = [
    path("", views.ClothReceiptListView.as_view(), name="list"),
    path("new/", views.ClothReceiptCreateView.as_view(), name="create"),
    path("sheet/", views.ReceivingSheetView.as_view(), name="sheet"),
    path("export-template/", views.ReceivingTemplateDownloadView.as_view(), name="export_template"),
    path("import/", views.ReceivingImportView.as_view(), name="import"),
    path("<int:pk>/", views.ClothReceiptDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.ClothReceiptUpdateView.as_view(), name="edit"),
    path("<int:pk>/cancel/", views.ClothReceiptCancelView.as_view(), name="cancel"),
]
