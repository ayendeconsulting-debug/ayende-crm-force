# customers/signals.py
"""
Django signals for customer model changes.
Triggers webhooks to POS system when customers are created, updated, or deleted.

FIXED:
- Changed instance.tenant to instance.tenants.first() for ManyToMany relationship
- Added check for webhook skip context to prevent circular webhooks during POS sync
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.conf import settings
from .models import Customer
import logging

logger = logging.getLogger(__name__)


def should_skip_webhooks():
    """
    Check if webhooks should be skipped in the current context.
    Imports the function from sync_views to check the context variable.
    
    Returns:
        bool: True if webhooks should be skipped
    """
    try:
        from dashboard.views.sync_views import should_skip_webhooks as check_skip
        return check_skip()
    except ImportError:
        # If sync_views not available, don't skip
        return False


@receiver(post_save, sender=Customer)
def customer_saved(sender, instance, created, **kwargs):
    """
    Signal handler for customer create/update events.
    Triggers webhook to POS system.
    
    This webhook is sent when:
    - Customer is created in CRM (not synced from POS)
    - Customer profile is updated in CRM (marketing, contact info changes)
    
    This webhook is NOT sent when:
    - Customer is being synced FROM POS (prevents circular webhooks)
    - We're in a skip_webhooks context
    
    Args:
        sender: The model class (Customer)
        instance: The actual customer instance being saved
        created: Boolean - True if this is a new customer
        **kwargs: Additional signal parameters
    """
    # Check if we're in a webhook skip context (during POS sync)
    if should_skip_webhooks():
        logger.debug(f"Skipping webhook during POS sync operation: {instance.id}")
        return
    
    # Only send webhooks if integration is enabled
    if not getattr(settings, 'ENABLE_CRM_SYNC', False):
        logger.debug(f"CRM sync disabled, skipping webhook for customer {instance.id}")
        return
    
    # Avoid triggering webhooks during bulk operations or migrations
    if kwargs.get('raw', False):
        logger.debug(f"Raw save detected, skipping webhook for customer {instance.id}")
        return
    
    try:
        # Import here to avoid circular imports
        from dashboard.services.webhook_service import WebhookService
        
        # Get the first tenant from ManyToMany relationship
        # FIXED: Changed from instance.tenant to instance.tenants.first()
        tenant = instance.tenants.first()
        
        if not tenant:
            logger.warning(f"Customer {instance.id} has no tenants, skipping webhook")
            return
        
        # Determine operation type
        operation = 'created' if created else 'updated'
        
        logger.info(f"Customer {operation}: {instance.id} ({instance.first_name} {instance.last_name})")
        
        # Send webhook asynchronously
        WebhookService.send_customer_webhook(
            customer=instance,
            operation=operation,
            tenant=tenant
        )
        
    except Exception as e:
        # Don't fail the save operation if webhook fails
        logger.error(f"Failed to send webhook for customer {instance.id}: {str(e)}", exc_info=True)


@receiver(post_delete, sender=Customer)
def customer_deleted(sender, instance, **kwargs):
    """
    Signal handler for customer delete events.
    Triggers webhook to POS system.
    
    Args:
        sender: The model class (Customer)
        instance: The customer instance being deleted
        **kwargs: Additional signal parameters
    """
    # Check if we're in a webhook skip context
    if should_skip_webhooks():
        logger.debug(f"Skipping delete webhook during sync operation: {instance.id}")
        return
    
    # Only send webhooks if integration is enabled
    if not getattr(settings, 'ENABLE_CRM_SYNC', False):
        logger.debug(f"CRM sync disabled, skipping delete webhook for customer {instance.id}")
        return
    
    try:
        # Import here to avoid circular imports
        from dashboard.services.webhook_service import WebhookService
        
        # Get the first tenant from ManyToMany relationship
        # FIXED: Changed from instance.tenant to instance.tenants.first()
        tenant = instance.tenants.first()
        
        if not tenant:
            logger.warning(f"Customer {instance.id} has no tenants, skipping delete webhook")
            return
        
        logger.info(f"Customer deleted: {instance.id} ({instance.first_name} {instance.last_name})")
        
        # Send webhook asynchronously
        WebhookService.send_customer_webhook(
            customer=instance,
            operation='deleted',
            tenant=tenant
        )
        
    except Exception as e:
        # Don't fail the delete operation if webhook fails
        logger.error(f"Failed to send delete webhook for customer {instance.id}: {str(e)}", exc_info=True)