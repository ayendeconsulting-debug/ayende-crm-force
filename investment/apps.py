from django.apps import AppConfig

class InvestmentConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'investment'
    verbose_name = 'Investment Lead Management'
    
    def ready(self):
        import investment.signals
