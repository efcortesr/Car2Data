import os
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.contrib.auth import get_user_model

@receiver(post_migrate)
def create_superuser_on_deploy(sender, **kwargs):
    if os.getenv("DJANGO_AUTO_CREATE_SUPERUSER", "false").lower() != "true":
        return
    username = os.getenv("DJANGO_SUPERUSER_USERNAME", "admin")
    email = os.getenv("DJANGO_SUPERUSER_EMAIL", "admin@example.com")
    password = os.getenv("DJANGO_SUPERUSER_PASSWORD", "admin123")
    User = get_user_model()
    if not User.objects.filter(username=username).exists():
        User.objects.create_superuser(username=username, email=email, password=password)
