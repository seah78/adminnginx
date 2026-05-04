from django.urls import path
from .views import (
    dashboard_home,
    site_create,
    site_list,
    site_detail,
    diagnostics_view,
    site_edit,
    nginx_reload_view,
    nginx_test_view,
    site_delete
)

urlpatterns = [
    path("", dashboard_home, name="dashboard"),
    path("sites/", site_list, name="site_list"),
    path("sites/new/", site_create, name="site_create"),
    path("sites/<str:filename>/edit/", site_edit, name="site_edit"),
    path("sites/<str:filename>/", site_detail, name="site_detail"),
    path("diagnostics/", diagnostics_view, name="diagnostics"),
    path("sites/<str:filename>/nginx-test/", nginx_test_view, name="nginx_test"),
    path("sites/<str:filename>/nginx-reload/", nginx_reload_view, name="nginx_reload"),
    path("sites/<str:filename>/delete/", site_delete, name="site_delete"),
]