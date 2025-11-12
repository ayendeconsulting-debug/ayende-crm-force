"""
Signals for Communications App
Automatically create notifications when messages are sent
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Message, Notification


@receiver(post_save, sender=Message)
def create_message_notification(sender, instance, created, **kwargs):
    """
    Automatically create notification when a message is sent to a customer
    """
    if created and instance.status == 'sent' and instance.receiver_customer:
        # Only create notification for business-to-customer or marketing messages
        if instance.message_type in ['business_to_customer', 'marketing']:
            Notification.create_for_message(instance)
