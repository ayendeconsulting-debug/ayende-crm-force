"""
Notification Models for Ayende CX
In-app notification system with category support and delivery tracking
"""

from django.db import models
from django.utils import timezone
import uuid


class Notification(models.Model):
    """
    Main notification model for storing notification content.
    Created by business owners to send to customers.
    """
    
    CATEGORY_CHOICES = [
        ('promotion', 'Promotion'),
        ('announcement', 'Announcement'),
        ('birthday', 'Birthday Greeting'),
        ('reminder', 'Reminder'),
        ('alert', 'Alert'),
        ('update', 'Update'),
        ('other', 'Other'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ]
    
    # Identification
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    created_by = models.ForeignKey(
        'customers.Customer',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_notifications',
        help_text="Business staff member who created this notification"
    )
    
    # Content
    title = models.CharField(
        max_length=200,
        help_text="Notification subject/title"
    )
    message = models.TextField(
        help_text="Main notification message content"
    )
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='announcement'
    )
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='normal'
    )
    
    # Targeting
    target_all_customers = models.BooleanField(
        default=True,
        help_text="Send to all active customers"
    )
    target_vip_only = models.BooleanField(
        default=False,
        help_text="Send only to VIP customers"
    )
    target_min_points = models.IntegerField(
        null=True,
        blank=True,
        help_text="Minimum loyalty points required"
    )
    target_max_points = models.IntegerField(
        null=True,
        blank=True,
        help_text="Maximum loyalty points (for targeting new customers)"
    )
    target_specific_customers = models.ManyToManyField(
        'customers.TenantCustomer',
        blank=True,
        related_name='targeted_notifications',
        help_text="Specific customers to target"
    )
    
    # Status & Scheduling
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )
    scheduled_for = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Schedule notification for future delivery"
    )
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When notification was actually sent"
    )
    
    # Statistics
    total_recipients = models.IntegerField(
        default=0,
        help_text="Total number of recipients"
    )
    total_delivered = models.IntegerField(
        default=0,
        help_text="Successfully delivered count"
    )
    total_read = models.IntegerField(
        default=0,
        help_text="Number of recipients who read the notification"
    )
    total_failed = models.IntegerField(
        default=0,
        help_text="Failed delivery count"
    )
    
    # Metadata
    notes = models.TextField(
        blank=True,
        help_text="Internal notes about this notification"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        indexes = [
            models.Index(fields=['tenant', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['category']),
            models.Index(fields=['scheduled_for']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.get_category_display()})"
    
    def get_target_customers(self):
        """
        Get queryset of customers who should receive this notification.
        Returns TenantCustomer queryset.
        """
        from customers.models import TenantCustomer
        
        # Start with all active customers in this tenant
        queryset = TenantCustomer.objects.filter(
            tenant=self.tenant,
            is_active=True,
            role='customer'  # Only regular customers, not staff
        )
        
        # Apply filters based on targeting settings
        if not self.target_all_customers:
            # If specific customers are targeted
            if self.target_specific_customers.exists():
                queryset = self.target_specific_customers.all()
            else:
                # If no specific customers but not targeting all, return empty
                return queryset.none()
        
        # Apply VIP filter
        if self.target_vip_only:
            queryset = queryset.filter(is_vip=True)
        
        # Apply points filters
        if self.target_min_points is not None:
            queryset = queryset.filter(loyalty_points__gte=self.target_min_points)
        
        if self.target_max_points is not None:
            queryset = queryset.filter(loyalty_points__lte=self.target_max_points)
        
        return queryset
    
    def send_notification(self):
        """
        Send notification to all targeted customers.
        Creates NotificationRecipient records for each customer.
        """
        if self.status == 'sent':
            return False  # Already sent
        
        # Get target customers
        target_customers = self.get_target_customers()
        
        if not target_customers.exists():
            self.status = 'failed'
            self.save()
            return False
        
        # Update status
        self.status = 'sending'
        self.save()
        
        # Create recipient records
        recipients_created = 0
        for tenant_customer in target_customers:
            recipient, created = NotificationRecipient.objects.get_or_create(
                notification=self,
                tenant_customer=tenant_customer,
                defaults={
                    'delivered_at': timezone.now(),
                    'delivery_status': 'delivered'
                }
            )
            if created:
                recipients_created += 1
        
        # Update statistics
        self.total_recipients = recipients_created
        self.total_delivered = recipients_created
        self.status = 'sent'
        self.sent_at = timezone.now()
        self.save()
        
        return True
    
    @property
    def read_rate(self):
        """Calculate percentage of recipients who read the notification"""
        if self.total_delivered > 0:
            return round((self.total_read / self.total_delivered) * 100, 1)
        return 0
    
    @property
    def is_scheduled(self):
        """Check if notification is scheduled for future"""
        if self.scheduled_for and self.status == 'scheduled':
            return self.scheduled_for > timezone.now()
        return False


class NotificationRecipient(models.Model):
    """
    Tracks delivery and read status for each recipient.
    Links notifications to individual customers.
    """
    
    DELIVERY_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
    ]
    
    # Identification
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name='recipients'
    )
    tenant_customer = models.ForeignKey(
        'customers.TenantCustomer',
        on_delete=models.CASCADE,
        related_name='received_notifications'
    )
    
    # Delivery Status
    delivery_status = models.CharField(
        max_length=20,
        choices=DELIVERY_STATUS_CHOICES,
        default='pending'
    )
    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When notification was delivered"
    )
    
    # Read Status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When customer read the notification"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notification_recipients'
        unique_together = ['notification', 'tenant_customer']
        ordering = ['-created_at']
        verbose_name = 'Notification Recipient'
        verbose_name_plural = 'Notification Recipients'
        indexes = [
            models.Index(fields=['tenant_customer', '-created_at']),
            models.Index(fields=['notification', 'is_read']),
            models.Index(fields=['is_read']),
        ]
    
    def __str__(self):
        return f"{self.notification.title} → {self.tenant_customer.customer.get_full_name()}"
    
    def mark_as_read(self):
        """Mark this notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()
            
            # Update notification statistics
            self.notification.total_read += 1
            self.notification.save(update_fields=['total_read'])
            
            return True
        return False
    
    def mark_as_unread(self):
        """Mark this notification as unread"""
        if self.is_read:
            self.is_read = False
            self.read_at = None
            self.save()
            
            # Update notification statistics
            self.notification.total_read -= 1
            self.notification.save(update_fields=['total_read'])
            
            return True
        return False
    
    @property
    def age_in_days(self):
        """Get age of notification in days"""
        if self.delivered_at:
            delta = timezone.now() - self.delivered_at
            return delta.days
        return 0
