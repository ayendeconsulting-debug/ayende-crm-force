from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
# REMOVED: from django.contrib.auth.models import User  ← Remove this line
from .models import InvestmentLead, LeadActivity
from .utils import send_lead_notification_email, send_investor_welcome_email


@receiver(post_save, sender=InvestmentLead)
def handle_new_lead(sender, instance, created, **kwargs):
    """
    Handle new lead creation:
    1. Auto-assign to adesanya@ayendecx.com
    2. Send email notification to admin@ayendecx.com
    3. Send welcome email to investor
    4. Log activity
    """
    if created:
        # Auto-assign to founder (adesanya@ayendecx.com)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            founder = User.objects.get(email='adesanya@ayendecx.com')
            instance.assigned_to = founder
            instance.save(update_fields=['assigned_to'])
        except User.DoesNotExist:
            try:
                founder = User.objects.filter(is_superuser=True).first()
                if founder:
                    instance.assigned_to = founder
                    instance.save(update_fields=['assigned_to'])
            except Exception:
                pass
        
        # Send notification email to admin@ayendecx.com (non-blocking)
        try:
            send_lead_notification_email(instance)
        except Exception as e:
            print(f"Email notification failed (non-critical): {e}")
        
        # Send welcome email to investor (non-blocking)
        try:
            send_investor_welcome_email(instance)
        except Exception as e:
            print(f"Welcome email failed (non-critical): {e}")
        
        # Log initial activity
        LeadActivity.objects.create(
            lead=instance,
            activity_type='note',
            subject='Lead Created',
            description=f'New investment lead received from {instance.source}. Lead score: {instance.lead_score}/100. Priority: {instance.priority.upper()}.',
            performed_by=instance.assigned_to
        )


@receiver(pre_save, sender=InvestmentLead)
def track_status_changes(sender, instance, **kwargs):
    """
    Track status changes and log as activity
    """
    if instance.pk:  # Only for existing leads
        try:
            old_instance = InvestmentLead.objects.get(pk=instance.pk)
            
            # Track status change
            if old_instance.status != instance.status:
                LeadActivity.objects.create(
                    lead=instance,
                    activity_type='status_change',
                    subject=f'Status changed from {old_instance.get_status_display()} to {instance.get_status_display()}',
                    description=f'Lead status updated from "{old_instance.get_status_display()}" to "{instance.get_status_display()}"',
                    performed_by=instance.assigned_to
                )
            
            # Track assignment change
            if old_instance.assigned_to != instance.assigned_to:
                new_assignee = instance.assigned_to.get_full_name() if instance.assigned_to else 'Unassigned'
                old_assignee = old_instance.assigned_to.get_full_name() if old_instance.assigned_to else 'Unassigned'
                
                LeadActivity.objects.create(
                    lead=instance,
                    activity_type='note',
                    subject='Lead Reassigned',
                    description=f'Lead reassigned from {old_assignee} to {new_assignee}',
                    performed_by=instance.assigned_to
                )
        except InvestmentLead.DoesNotExist:
            pass