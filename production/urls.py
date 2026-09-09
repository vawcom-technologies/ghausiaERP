from django.urls import path

from production import views

app_name = "production"

urlpatterns = [
    path("lots/", views.ProductionLotListView.as_view(), name="lot_list"),
    path("lots/export/", views.ProductionLotExportView.as_view(), name="lot_export"),
    path("lots/<int:pk>/", views.ProductionLotDetailView.as_view(), name="lot_detail"),
    path("lots/<int:pk>/complete-dyeing/", views.CompleteDyeingView.as_view(), name="complete_dyeing"),
    path("singeing/", views.SingeingListView.as_view(), name="singeing_list"),
    path("singeing/new/", views.SingeingCreateView.as_view(), name="singeing_create"),
    path("singeing/<int:pk>/", views.SingeingDetailView.as_view(), name="singeing_detail"),
    path("singeing/<int:pk>/cancel/", views.SingeingCancelView.as_view(), name="singeing_cancel"),
    path("dyeing/", views.DyeingListView.as_view(), name="dyeing_list"),
    path("dyeing/new/", views.DyeingCreateView.as_view(), name="dyeing_create"),
    path("dyeing/<int:pk>/", views.DyeingDetailView.as_view(), name="dyeing_detail"),
    path("dyeing/<int:pk>/cancel/", views.DyeingCancelView.as_view(), name="dyeing_cancel"),
    path("dyeing/material/new/", views.DyeingMaterialUsageCreateView.as_view(), name="dyeing_material_create"),
    path("dyeing/material/<int:pk>/cancel/", views.DyeingMaterialUsageCancelView.as_view(), name="dyeing_material_cancel"),
    path("mixtures/new/", views.MixtureCreateView.as_view(), name="mixture_create"),
    path("mixtures/<int:pk>/", views.MixtureDetailView.as_view(), name="mixture_detail"),
    path("mixtures/<int:pk>/cancel/", views.MixtureCancelView.as_view(), name="mixture_cancel"),
    path("mixtures/ingredient/new/", views.MixtureIngredientCreateView.as_view(), name="mixture_ingredient_create"),
    path("mixtures/ingredient/<int:pk>/cancel/", views.MixtureIngredientCancelView.as_view(), name="mixture_ingredient_cancel"),
    path("six-chamber/", views.SixChamberListView.as_view(), name="sixchamber_list"),
    path("six-chamber/new/", views.SixChamberCreateView.as_view(), name="sixchamber_create"),
    path("six-chamber/<int:pk>/", views.SixChamberDetailView.as_view(), name="sixchamber_detail"),
    path("six-chamber/<int:pk>/cancel/", views.SixChamberCancelView.as_view(), name="sixchamber_cancel"),
    path("calender/", views.CalenderListView.as_view(), name="calender_list"),
    path("calender/new/", views.CalenderCreateView.as_view(), name="calender_create"),
    path("calender/<int:pk>/", views.CalenderDetailView.as_view(), name="calender_detail"),
    path("calender/<int:pk>/cancel/", views.CalenderCancelView.as_view(), name="calender_cancel"),
    path("comfort/", views.ComfortListView.as_view(), name="comfort_list"),
    path("comfort/new/", views.ComfortCreateView.as_view(), name="comfort_create"),
    path("comfort/<int:pk>/", views.ComfortDetailView.as_view(), name="comfort_detail"),
    path("comfort/<int:pk>/cancel/", views.ComfortCancelView.as_view(), name="comfort_cancel"),
    path("finished/", views.FinishedStockListView.as_view(), name="finished_list"),
    path("finished/new/", views.FinishedStockCreateView.as_view(), name="finished_create"),
    path("finished/<int:pk>/", views.FinishedStockDetailView.as_view(), name="finished_detail"),
    path("finished/<int:pk>/cancel/", views.FinishedStockCancelView.as_view(), name="finished_cancel"),
]
