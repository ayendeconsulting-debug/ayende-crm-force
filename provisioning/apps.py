"""
Provisioning App Configuration

Location: provisioning/apps.py
"""

from django.apps import AppConfig


class ProvisioningConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'provisioning'
    verbose_name = 'CRM Provisioning'