from django.urls import path
from .views import (
    dashboard_home,
    site_create,
    site_list,
    site_detail,
    diagnostics_view,
)

urlpatterns = [
    path("", dashboard_home, name="dashboard"),
    path("sites/", site_list, name="site_list"),
    path("sites/new/", site_create, name="site_create"),
    path("sites/<str:filename>/", site_detail, name="site_detail"),
    path("diagnostics/", diagnostics_view, name="diagnostics"),
]