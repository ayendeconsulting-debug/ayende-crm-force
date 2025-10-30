# customers/apps.py
"""
Customer app configuration.
Registers signals for webhook triggers.
"""

from django.apps import AppConfig


class CustomersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'customers'
    
    def ready(self):
        """
        Import signals when app is ready.
        This ensures signal handlers are registered.
        """
        import customers.signals  # noqa
