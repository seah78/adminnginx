from django.urls import path

from .views import (
    dashboard_home,
    site_create,
    site_list,
    site_detail,
    site_edit,
    site_delete,
    nginx_test_view,
    nginx_reload_view,
    diagnostics_view,
    operation_progress,
    operation_status,
    security_view,
    two_factor_setup,
    two_factor_disable,
)


urlpatterns = [
    path("", dashboard_home, name="dashboard"),

    path("sites/", site_list, name="site_list"),
    path("sites/new/", site_create, name="site_create"),
    path("sites/<str:filename>/edit/", site_edit, name="site_edit"),
    path("sites/<str:filename>/delete/", site_delete, name="site_delete"),
    path("sites/<str:filename>/nginx-test/", nginx_test_view, name="nginx_test"),
    path("sites/<str:filename>/nginx-reload/", nginx_reload_view, name="nginx_reload"),
    path("sites/<str:filename>/", site_detail, name="site_detail"),
    path("diagnostics/", diagnostics_view, name="diagnostics"),
    path("operations/<str:operation_id>/", operation_progress, name="operation_progress"),
    path("operations/<str:operation_id>/status/", operation_status, name="operation_status"),
    path("security/", security_view, name="security"),
    path("security/2fa/setup/", two_factor_setup, name="two_factor_setup"),
    path("security/2fa/disable/", two_factor_disable, name="two_factor_disable"),
]