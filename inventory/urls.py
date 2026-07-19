from django.urls import path

from inventory import views

app_name = "inventory"

urlpatterns = [
    path("", views.InventoryHomeView.as_view(), name="home"),
    path("transactions/", views.MaterialTransactionListView.as_view(), name="transaction_list"),
    path("transactions/<int:pk>/", views.MaterialTransactionDetailView.as_view(), name="transaction_detail"),
    path("purchase/new/", views.PurchaseCreateView.as_view(), name="purchase_create"),
    path("purchase/sheet/", views.PurchaseSheetView.as_view(), name="purchase_sheet"),
    path("purchase/export-template/", views.PurchaseTemplateDownloadView.as_view(), name="purchase_export_template"),
    path("purchase/import/", views.PurchaseImportView.as_view(), name="purchase_import"),
    path("adjustment-in/new/", views.AdjustmentInCreateView.as_view(), name="adjustment_in_create"),
    path("adjustment-out/new/", views.AdjustmentOutCreateView.as_view(), name="adjustment_out_create"),
    path("stock/", views.StockOverviewView.as_view(), name="stock_overview"),
]
