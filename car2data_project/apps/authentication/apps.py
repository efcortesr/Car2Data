from django.apps import AppConfig


class AuthenticationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.authentication'
    verbose_name = 'Autenticación'

    def ready(self):
        # Import signals so post_migrate hook registers
        from . import signals  # noqa: F401
