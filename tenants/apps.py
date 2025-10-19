"""
Tenants app configuration
"""

from django.apps import AppConfig


class TenantsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tenants'
    verbose_name = 'Business Tenants'
    
    def ready(self):
        """
        Import signals when app is ready
        """
        import tenants.signals