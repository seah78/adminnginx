from django.contrib.auth.signals import user_logged_in


def user_logged_in_handler(sender, request, user, **kwargs):
    request.session["two_factor_verified"] = False


user_logged_in.connect(user_logged_in_handler)