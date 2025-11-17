# customers/signals.py
"""
Django signals for customer model changes.
Triggers webhooks to POS system when customers are created, updated, or deleted.

UPDATED: Added signals for TenantCustomer model
- Listens to BOTH Customer (global) and TenantCustomer (tenant-specific)
- Sends webhooks when TenantCustomer is updated (CRM UI edits)
- Prevents duplicate webhooks with proper context checking

ARCHITECTURE:
- Customer: Global identity (name, DOB) - shared across tenants
- TenantCustomer: Tenant-specific data (email, phone, loyalty) - edited in CRM UI

CHANGELOG:
- Added TenantCustomer signals for real-time sync
- Webhook now triggers when user edits customer in CRM
- Both models can trigger webhooks (with duplicate prevention)
"""

from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.conf import settings
from .models import Customer, TenantCustomer
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


# ============================================================================
# GLOBAL CUSTOMER SIGNALS (for admin/API changes)
# ============================================================================

@receiver(post_save, sender=Customer)
def customer_saved(sender, instance, created, **kwargs):
    """
    Signal handler for global Customer create/update events.
    
    NOTE: This fires when Customer is changed directly (rare - usually admin/API).
    Most CRM UI edits go through TenantCustomer and trigger tenant_customer_saved instead.
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
        operation = 'updated'  # Default to update

        if created:
            operation = 'created'
            logger.info(f"Customer created (admin): {instance.id} ({instance.first_name} {instance.last_name})")
        elif not instance.external_id:
            operation = 'created'
            logger.info(f"Customer first sync (registration): {instance.id} ({instance.first_name} {instance.last_name})")
        else:
            operation = 'updated'
            logger.info(f"Customer updated: {instance.id} ({instance.first_name} {instance.last_name})")   

        # Send webhook asynchronously
        WebhookService.send_customer_webhook(
            customer=instance,  # FIXED: Use instance, not undefined 'customer'
            operation=operation,
            tenant=tenant
        )

    except Exception as e:
        # Don't fail the save operation if webhook fails
        logger.error(f"Failed to send webhook for customer {instance.id}: {str(e)}", exc_info=True)        


@receiver(post_delete, sender=Customer)
def customer_deleted(sender, instance, **kwargs):
    """
    Signal handler for global Customer delete events.
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


# ============================================================================
# TENANT CUSTOMER SIGNALS (for CRM UI edits) - NEW!
# ============================================================================

@receiver(post_save, sender=TenantCustomer)
def tenant_customer_saved(sender, instance, created, **kwargs):
    """
    Signal handler for TenantCustomer create/update events.
    
    IMPORTANT: This is what triggers when users edit customers in the CRM UI!
    The CRM UI edits TenantCustomer (email, phone, loyalty, etc), not Customer.
    
    This webhook is sent when:
    - Customer profile edited in CRM UI (name, email, phone, loyalty changes)
    - TenantCustomer created during registration
    
    This webhook is NOT sent when:
    - Customer is being synced FROM POS (prevents circular webhooks)
    - We're in a skip_webhooks context
    """
    # Check if we're in a webhook skip context (during POS sync)
    if should_skip_webhooks():
        logger.debug(f"Skipping TenantCustomer webhook during POS sync: {instance.id}")
        return

    # Only send webhooks if integration is enabled
    if not getattr(settings, 'ENABLE_CRM_SYNC', False):
        logger.debug(f"CRM sync disabled, skipping TenantCustomer webhook: {instance.id}")
        return

    # Avoid triggering webhooks during bulk operations or migrations
    if kwargs.get('raw', False):
        logger.debug(f"Raw save detected, skipping TenantCustomer webhook: {instance.id}")
        return

    try:
        # Import here to avoid circular imports
        from dashboard.services.webhook_service import WebhookService

        # Get the global Customer instance
        customer = instance.customer if hasattr(instance, 'customer') else None
        
        if not customer:
            # Try to find customer through reverse relationship
            from .models import Customer
            customer = Customer.objects.filter(
                tenant_accounts=instance
            ).first()
        
        if not customer:
            logger.error(f"No global Customer found for TenantCustomer {instance.id}")
            return

        # Get tenant
        tenant = instance.tenant

        # Determine operation type
        operation = 'updated'  # Most CRM UI edits are updates

        if created:
            # Brand new TenantCustomer
            operation = 'created'
            logger.info(f"TenantCustomer created: {instance.id} ({instance.first_name} {instance.last_name})")
        elif not instance.external_id:
            # TenantCustomer exists but never synced to POS
            operation = 'created'
            logger.info(f"TenantCustomer first sync: {instance.id} ({instance.first_name} {instance.last_name})")
        else:
            # Regular update (THIS IS WHAT FIRES WHEN YOU EDIT IN CRM UI)
            operation = 'updated'
            logger.info(f"✏️ TenantCustomer updated in CRM UI: {instance.id} ({instance.first_name} {instance.last_name})")

        # Send webhook asynchronously
        WebhookService.send_customer_webhook(
            customer=customer,  # Send global customer
            operation=operation,
            tenant=tenant,
            tenant_customer=instance  # Pass TenantCustomer instance directly!
        )

    except Exception as e:
        # Don't fail the save operation if webhook fails
        logger.error(f"Failed to send TenantCustomer webhook: {str(e)}", exc_info=True)


@receiver(post_delete, sender=TenantCustomer)
def tenant_customer_deleted(sender, instance, **kwargs):
    """
    Signal handler for TenantCustomer delete events.
    Typically happens when customer is removed from a tenant.
    """
    # Check if we're in a webhook skip context
    if should_skip_webhooks():
        logger.debug(f"Skipping TenantCustomer delete webhook during sync: {instance.id}")
        return

    # Only send webhooks if integration is enabled
    if not getattr(settings, 'ENABLE_CRM_SYNC', False):
        logger.debug(f"CRM sync disabled, skipping TenantCustomer delete webhook")
        return

    try:
        # Import here to avoid circular imports
        from dashboard.services.webhook_service import WebhookService

        # Get the global Customer instance
        customer = instance.customer if hasattr(instance, 'customer') else None
        
        if not customer:
            logger.warning(f"No global Customer found for deleted TenantCustomer {instance.id}")
            return

        tenant = instance.tenant

        logger.info(f"TenantCustomer deleted: {instance.id} ({instance.first_name} {instance.last_name})")

        # Send webhook asynchronously
        WebhookService.send_customer_webhook(
            customer=customer,
            operation='deleted',
            tenant=tenant,
            tenant_customer=instance  # Pass TenantCustomer instance directly!
        )

    except Exception as e:
        # Don't fail the delete operation if webhook fails
        logger.error(f"Failed to send TenantCustomer delete webhook: {str(e)}", exc_info=True)


# ============================================================================
# M2M SIGNALS (for tenant assignment)
# ============================================================================

@receiver(m2m_changed, sender=Customer.tenants.through)
def customer_tenant_changed(sender, instance, action, **kwargs):
    """
    Signal handler for customer-tenant relationship changes.
    Triggers webhook when customer gets their first tenant assigned.

    This handles the registration flow where:
    1. Customer is created without tenant
    2. Tenant is assigned via TenantCustomer.objects.create()
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