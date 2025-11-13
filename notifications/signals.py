"""
Automated Messaging Signals - Configurable via Tenant Settings
Handles event-triggered messages with settings from TenantSettings model
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from customers.models import TenantCustomer, Transaction
from notifications.models import Message, MessageTemplate


@receiver(post_save, sender=TenantCustomer)
def send_welcome_message(sender, instance, created, **kwargs):
    """
    Automatically send welcome message when new customer registers.
    Configurable via tenant.settings.welcome_bonus_enabled and welcome_bonus_points
    """
    # Skip if no tenant
    if not instance.tenant:
        return
    
    tenant = instance.tenant
    
    # Check if welcome bonus is enabled (from tenant settings)
    try:
        settings = tenant.settings
        if not settings.welcome_bonus_enabled:
            print(f"⏭️  Welcome messages disabled for {tenant.name}")
            return
        bonus_points = settings.welcome_bonus_points
    except:
        # Fallback to defaults if settings don't exist
        bonus_points = 100
    
    if created and instance.role == 'customer' and instance.email_verified:
        # Get or create welcome template
        template, template_created = MessageTemplate.objects.get_or_create(
            tenant=tenant,
            template_type='welcome',
            defaults={
                'name': 'Welcome Message',
                'subject': 'Welcome to {{business_name}}!',
                'body': f'''Hi {{{{first_name}}}}!

Welcome to {{{{business_name}}}} family.
As a token of our appreciation for joining our loyalty program, we are crediting you {bonus_points} points.

Hope to see you at our store soon.

{{{{business_name}}}}''',
                'created_by': None
            }
        )
        
        # Award bonus points
        instance.loyalty_points += bonus_points
        instance.save(update_fields=['loyalty_points'])
        
        # Render template with customer data
        subject, body = template.render(instance)
        
        # Create message with RENDERED content
        Message.objects.create(
            tenant=tenant,
            sender=None,
            receiver=instance,
            message_type='business_to_customer',
            subject=subject,
            body=body,
            priority='normal',
            status='sent',
            sent_at=timezone.now(),
            template_used=template
        )
        
        template.increment_usage()
        print(f"✅ Sent welcome message to {instance.email} (+{bonus_points} points)")


@receiver(post_save, sender=TenantCustomer)
def send_loyalty_milestone_message(sender, instance, created, **kwargs):
    """
    Send congratulations message when customer reaches loyalty milestones.
    Configurable via tenant.settings.loyalty_milestone_enabled and loyalty_milestones
    """
    # Skip if no tenant or not a customer
    if not instance.tenant or instance.role != 'customer':
        return
    
    tenant = instance.tenant
    
    # Check if milestone messages are enabled
    try:
        settings = tenant.settings
        if not settings.loyalty_milestone_enabled:
            return
        milestones = settings.loyalty_milestones if settings.loyalty_milestones else [100, 500, 1000, 2500, 5000]
    except:
        milestones = [100, 500, 1000, 2500, 5000]  # Default
    
    if not created:
        current_points = instance.loyalty_points
        
        # Get the old value from database (before save)
        try:
            old_instance = TenantCustomer.objects.get(pk=instance.pk)
            old_points = old_instance.loyalty_points
        except TenantCustomer.DoesNotExist:
            return
        
        # Check if just crossed a milestone
        for milestone in milestones:
            if old_points < milestone <= current_points:
                # Get or create milestone template
                template, _ = MessageTemplate.objects.get_or_create(
                    tenant=tenant,
                    template_type='reward',
                    name=f'Milestone {milestone} Points',
                    defaults={
                        'subject': f'Congratulations! You reached {milestone} points!',
                        'body': f'''Hi {{{{first_name}}}}!

Congratulations on reaching {milestone} loyalty points at {{{{business_name}}}}!

You're now eligible for exclusive rewards. Visit us to redeem your points!

Thank you for being a valued customer.

{{{{business_name}}}}''',
                        'created_by': None
                    }
                )
                
                # Render and send
                subject, body = template.render(instance)
                
                Message.objects.create(
                    tenant=tenant,
                    sender=None,
                    receiver=instance,
                    message_type='business_to_customer',
                    subject=subject,
                    body=body,
                    priority='high',
                    status='sent',
                    sent_at=timezone.now(),
                    template_used=template
                )
                
                template.increment_usage()
                print(f"✅ Sent milestone message ({milestone} points) to {instance.email}")
                break


@receiver(post_save, sender=Transaction)
def send_large_purchase_thank_you(sender, instance, created, **kwargs):
    """
    Send thank you message for large purchases.
    Configurable via tenant.settings.large_purchase_enabled and large_purchase_threshold
    """
    # Skip if no tenant or customer
    if not instance.tenant or not instance.tenant_customer:
        return
    
    tenant = instance.tenant
    customer = instance.tenant_customer
    
    # Check if large purchase messages are enabled
    try:
        settings = tenant.settings
        if not settings.large_purchase_enabled:
            return
        threshold = settings.large_purchase_threshold
    except:
        threshold = 100.00  # Default
    
    if created and instance.status == 'completed' and instance.total >= threshold:
        # Get or create thank you template
        template, _ = MessageTemplate.objects.get_or_create(
            tenant=tenant,
            template_type='thank_you',
            name='Large Purchase Thank You',
            defaults={
                'subject': 'Thank you for your purchase!',
                'body': '''Hi {{first_name}}!

Thank you for your recent purchase at {{business_name}}!

We appreciate your business and hope you're satisfied with your purchase. 
You earned loyalty points with this transaction.

See you again soon!

{{business_name}}''',
                'created_by': None
            }
        )
        
        # Render and send
        subject, body = template.render(customer)
        
        Message.objects.create(
            tenant=tenant,
            sender=None,
            receiver=customer,
            message_type='business_to_customer',
            subject=subject,
            body=body,
            priority='normal',
            status='sent',
            sent_at=timezone.now(),
            template_used=template
        )
        
        template.increment_usage()
        print(f"✅ Sent thank you message to {customer.email} for ${instance.total} purchase")