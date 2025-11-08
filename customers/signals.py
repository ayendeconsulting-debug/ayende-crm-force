# customers/signals.py
"""
Django signals for customer model changes.
Triggers webhooks to POS system when customers are created, updated, or deleted.

UPDATED: Fixed customer creation detection for two-step registration process
- Detects when customer gets first tenant assigned (treats as 'created')
- Prevents sending webhooks for customers without tenants
- Still handles normal updates correctly

CHANGELOG:
- Changed instance.tenant to instance.tenants.first() for ManyToMany relationship
- Added check for webhook skip context to prevent circular webhooks during POS sync
- Added first-tenant detection logic to properly identify customer creation
"""

from django.db.models.signals import post_save, post_delete, m2m_changed
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
    
    IMPORTANT: Due to the two-step registration process (create customer, then assign tenant),
    we can't rely on the 'created' parameter alone. Instead, we check if this is the first
    time the customer has a tenant assigned.
    
    This webhook is sent when:
    - Customer is created AND has a tenant assigned
    - Customer profile is updated in CRM (marketing, contact info changes)
    
    This webhook is NOT sent when:
    - Customer is created but has NO tenant yet (registration step 1)
    - Customer is being synced FROM POS (prevents circular webhooks)
    - We're in a skip_webhooks context
    
    Args:
        sender: The model class (Customer)
        instance: The actual customer instance being saved
        created: Boolean - True if this is a new customer (may not have tenant yet)
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
        tenant = instance.tenants.first()
        
        if not tenant:
            logger.warning(f"Customer {instance.id} has no tenants, skipping webhook")
            return
        
        # Determine operation type
        # We can't just use 'created' because of the two-step registration:
        # 1. Customer created without tenant -> created=True, but no tenant -> webhook skipped
        # 2. Tenant assigned later -> created=False, but this is first webhook -> should be 'created'
        #
        # Solution: Check if customer has external_id. If not, this is the first sync to POS.
        operation = 'updated'  # Default to update
        
        if created:
            # Brand new customer with tenant already assigned (e.g., Django admin creation)
            operation = 'created'
            logger.info(f"Customer created (admin): {instance.id} ({instance.first_name} {instance.last_name})")
        elif not instance.external_id:
            # Customer exists in CRM but has no external_id (POS ID)
            # This means it's never been synced to POS before -> treat as creation
            operation = 'created'
            logger.info(f"Customer first sync (registration): {instance.id} ({instance.first_name} {instance.last_name})")
        else:
            # Customer has external_id, so it exists in POS -> this is an update
            operation = 'updated'
            logger.info(f"Customer updated: {instance.id} ({instance.first_name} {instance.last_name})")
        
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


# Alternative approach: Detect tenant assignment via m2m_changed signal
# This catches when a tenant is added to a customer's tenants ManyToMany field
@receiver(m2m_changed, sender=Customer.tenants.through)
def customer_tenant_changed(sender, instance, action, **kwargs):
    """
    Signal handler for customer-tenant relationship changes.
    Triggers webhook when customer gets their first tenant assigned.
    
    This handles the registration flow where:
    1. Customer is created without tenant
    2. Tenant is assigned via TenantCustomer.objects.create()
    
    Args:
        sender: The through model (TenantCustomer)
        instance: The customer instance
        action: The m2m action (pre_add, post_add, pre_remove, post_remove, etc.)
        **kwargs: Additional signal parameters
    """
    # Only care about post_add (after tenant is added)
    if action != 'post_add':
        return
    
    # Check if we're in a webhook skip context
    if should_skip_webhooks():
        logger.debug(f"Skipping tenant-assignment webhook during sync: {instance.id}")
        return
    
    # Only send webhooks if integration is enabled
    if not getattr(settings, 'ENABLE_CRM_SYNC', False):
        logger.debug(f"CRM sync disabled, skipping tenant-assignment webhook")
        return
    
    try:
        # Check if this is the first tenant being added
        tenant_count = instance.tenants.count()
        
        if tenant_count == 1 and not instance.external_id:
            # First tenant added AND no POS ID yet -> this is a new customer registration
            logger.info(
                f"First tenant assigned to customer {instance.id} ({instance.first_name} {instance.last_name})"
            )
            
            # Import here to avoid circular imports
            from dashboard.services.webhook_service import WebhookService
            
            tenant = instance.tenants.first()
            
            # Send 'created' webhook
            WebhookService.send_customer_webhook(
                customer=instance,
                operation='created',
                tenant=tenant
            )
        else:
            logger.debug(f"Tenant added to existing customer {instance.id}, not sending creation webhook")
            
    except Exception as e:
        logger.error(
            f"Failed to send tenant-assignment webhook for customer {instance.id}: {str(e)}", 
            exc_info=True
        )