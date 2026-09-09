from django.urls import path

from master_data import views

app_name = "master_data"

urlpatterns = [
    path("setup/", views.SetupHomeView.as_view(), name="setup"),
    path("vendors/", views.VendorListView.as_view(), name="vendor_list"),
    path("vendors/export/", views.VendorExportView.as_view(), name="vendor_export"),
    path("vendors/new/", views.VendorCreateView.as_view(), name="vendor_create"),
    path("vendors/<int:pk>/", views.VendorDetailView.as_view(), name="vendor_detail"),
    path("vendors/<int:pk>/edit/", views.VendorUpdateView.as_view(), name="vendor_edit"),
    path("cloth-types/", views.ClothTypeListView.as_view(), name="clothtype_list"),
    path("cloth-types/export/", views.ClothTypeExportView.as_view(), name="clothtype_export"),
    path("cloth-types/new/", views.ClothTypeCreateView.as_view(), name="clothtype_create"),
    path("cloth-types/<int:pk>/", views.ClothTypeDetailView.as_view(), name="clothtype_detail"),
    path("cloth-types/<int:pk>/edit/", views.ClothTypeUpdateView.as_view(), name="clothtype_edit"),
    path("employees/", views.EmployeeListView.as_view(), name="employee_list"),
    path("employees/export/", views.EmployeeExportView.as_view(), name="employee_export"),
    path("employees/new/", views.EmployeeCreateView.as_view(), name="employee_create"),
    path("employees/<int:pk>/", views.EmployeeDetailView.as_view(), name="employee_detail"),
    path("employees/<int:pk>/edit/", views.EmployeeUpdateView.as_view(), name="employee_edit"),
    path("machines/", views.MachineListView.as_view(), name="machine_list"),
    path("machines/export/", views.MachineExportView.as_view(), name="machine_export"),
    path("machines/new/", views.MachineCreateView.as_view(), name="machine_create"),
    path("machines/<int:pk>/", views.MachineDetailView.as_view(), name="machine_detail"),
    path("machines/<int:pk>/edit/", views.MachineUpdateView.as_view(), name="machine_edit"),
    path("materials/", views.MaterialListView.as_view(), name="material_list"),
    path("materials/export/", views.MaterialExportView.as_view(), name="material_export"),
    path("materials/new/", views.MaterialCreateView.as_view(), name="material_create"),
    path("materials/<int:pk>/", views.MaterialDetailView.as_view(), name="material_detail"),
    path("materials/<int:pk>/edit/", views.MaterialUpdateView.as_view(), name="material_edit"),
]
