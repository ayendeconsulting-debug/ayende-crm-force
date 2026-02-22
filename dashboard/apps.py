from django.apps import AppConfig


class DashboardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'dashboard'
    
    def ready(self):
        """Import health checks to register them with django-health-check"""
        try:
            from . import health_checks  # noqa: F401
        except ImportError:
            pass