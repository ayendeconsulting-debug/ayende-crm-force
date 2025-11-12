"""
Communications App Configuration
"""

from django.apps import AppConfig


class CommunicationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'communications'
    verbose_name = 'Communications'
    
    def ready(self):
        """Import signals when app is ready"""
        try:
            import communications.signals
        except ImportError:
            pass
