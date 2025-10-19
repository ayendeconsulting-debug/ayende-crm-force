"""
Signals for Tenant models
Auto-creates related objects when a Tenant is created
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Tenant, TenantSettings


@receiver(post_save, sender=Tenant)
def create_tenant_settings(sender, instance, created, **kwargs):
    """
    Automatically create TenantSettings when a new Tenant is created
    """
    if created:
        TenantSettings.objects.create(tenant=instance)
        print(f"✓ TenantSettings created for {instance.name}")


@receiver(post_save, sender=Tenant)
def save_tenant_settings(sender, instance, **kwargs):
    """
    Save TenantSettings when Tenant is saved
    """
    if hasattr(instance, 'settings'):
        instance.settings.save()