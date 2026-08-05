from django.contrib.auth import views as auth_views
from django.urls import path

from accounts.views import HomeView, ProfileView, RestoreDeletedView, UserListView

app_name = "accounts"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path(
        "profile/restore/<str:model_key>/<int:pk>/",
        RestoreDeletedView.as_view(),
        name="restore_deleted",
    ),
    path("users/", UserListView.as_view(), name="users"),
]
