from django.contrib.auth import views as auth_views
from django.urls import path

from accounts.staff_views import (
    AssignmentDashboardView,
    CreateJobAccountsView,
    StaffUserCreateView,
    ToggleUserActiveView,
    UserListView,
)
from accounts.views import ERPLoginView, HomeView, ProfileView, RestoreDeletedView

app_name = "accounts"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("login/", ERPLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path(
        "profile/restore/<str:model_key>/<int:pk>/",
        RestoreDeletedView.as_view(),
        name="restore_deleted",
    ),
    path("users/", UserListView.as_view(), name="users"),
    path("users/new/", StaffUserCreateView.as_view(), name="user_create"),
    path("users/job-accounts/", CreateJobAccountsView.as_view(), name="job_accounts"),
    path("users/<int:pk>/toggle/", ToggleUserActiveView.as_view(), name="user_toggle"),
    path("users/assignments/", AssignmentDashboardView.as_view(), name="assignments"),
]
