from django.apps import AppConfig


class AuthenticationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.authentication'

    def ready(self):
        from django.contrib import admin

        from .admin_guard import protected_admin_has_permission

        admin.site.has_permission = protected_admin_has_permission
