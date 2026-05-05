from django.shortcuts import redirect
from django.urls import reverse
from django_otp.plugins.otp_totp.models import TOTPDevice

# non indexation des pages
class NoIndexMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["X-Robots-Tag"] = "noindex, nofollow, noarchive, nosnippet"
        return response


# 2FA
class RequireTwoFactorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

        allowed_paths = [
            reverse("two_factor_verify"),
            reverse("logout"),
        ]

        if request.path in allowed_paths:
            return self.get_response(request)

        has_2fa = TOTPDevice.objects.filter(
            user=request.user,
            confirmed=True,
        ).exists()

        if has_2fa and not request.session.get("two_factor_verified"):
            return redirect("two_factor_verify")

        return self.get_response(request)