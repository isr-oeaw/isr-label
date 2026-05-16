"""Create numbered test users for local development."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Create numbered test users (e.g. testuser1 … testuser10). "
        "Skips usernames that already exist."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=10,
            help="Number of users to create (default: 10).",
        )
        parser.add_argument(
            "--password",
            default="testpass123",
            help="Password for each new user (default: testpass123).",
        )
        parser.add_argument(
            "--prefix",
            default="testuser",
            help="Username prefix; users are {prefix}1 … {prefix}N (default: testuser).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Allow running when DEBUG is False (use with care).",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            raise CommandError(
                "DEBUG is False. Run with --force if you still want to create users."
            )

        count = options["count"]
        if count < 1 or count > 500:
            raise CommandError("--count must be between 1 and 500.")

        password = options["password"]
        prefix = options["prefix"].strip()
        if not prefix:
            raise CommandError("--prefix must not be empty.")

        created = 0
        skipped = 0
        for i in range(1, count + 1):
            username = f"{prefix}{i}"
            email = f"{username}@dev.local"
            if User.objects.filter(username=username).exists():
                skipped += 1
                self.stdout.write(self.style.WARNING(f"Skip (exists): {username}"))
                continue
            User.objects.create_user(
                username=username,
                email=email,
                password=password,
            )
            created += 1
            self.stdout.write(self.style.SUCCESS(f"Created: {username} ({email})"))

        self.stdout.write(
            self.style.NOTICE(f"Done. Created {created}, skipped {skipped}. Password: {password!r}")
        )
