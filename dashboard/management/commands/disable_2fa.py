from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django_otp.plugins.otp_totp.models import TOTPDevice


class Command(BaseCommand):
    help = "Disable 2FA for a user."

    def add_arguments(self, parser):
        parser.add_argument("username", type=str)

    def handle(self, *args, **options):
        username = options["username"]

        User = get_user_model()

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist as error:
            raise CommandError(
                f"User '{username}' does not exist."
            ) from error

        deleted_count, _ = TOTPDevice.objects.filter(
            user=user,
        ).delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"2FA disabled for '{username}'. Devices deleted: {deleted_count}"
            )
        )