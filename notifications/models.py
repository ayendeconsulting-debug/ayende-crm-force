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
        'customers.TenantCustomer',
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

# ============================================
   # ENHANCED COMMUNICATION MODELS
   # Two-way messaging, templates, attachments
   # ============================================
    """
Enhanced Communication Models
Add these models to your existing notifications/models.py file

These models add:
1. Two-way messaging (Message model)
2. Message templates with variables (MessageTemplate model)
3. Message threading support
"""

from django.db import models
from django.utils import timezone
import uuid


class Message(models.Model):
    """
    Two-way messaging between customers and business staff.
    Supports conversations and threading.
    """
    MESSAGE_TYPE_CHOICES = [
        ('customer_to_business', 'Customer to Business'),
        ('business_to_customer', 'Business to Customer'),
        ('internal', 'Internal Note'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('read', 'Read'),
        ('archived', 'Archived'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    # Identification
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(
        'customers.TenantCustomer',
        on_delete=models.SET_NULL,
        null=True,
        related_name='sent_messages',
        help_text='Person who sent the message'
    )
    receiver = models.ForeignKey(
        'customers.TenantCustomer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='received_messages',
        help_text='Specific recipient (null = all staff)'
    )
    
    # Message Content
    message_type = models.CharField(
        max_length=30,
        choices=MESSAGE_TYPE_CHOICES,
        default='business_to_customer'
    )
    subject = models.CharField(max_length=255)
    body = models.TextField()
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='normal'
    )
    
    # Status & Tracking
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Threading (for conversations)
    parent_message = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='replies',
        help_text='Parent message for threading'
    )
    
    # Template reference
    template_used = models.ForeignKey(
        'MessageTemplate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text='Template used to create this message'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'messages'
        ordering = ['-created_at']
        verbose_name = 'Message'
        verbose_name_plural = 'Messages'
        indexes = [
            models.Index(fields=['tenant', '-created_at']),
            models.Index(fields=['receiver', 'status']),
            models.Index(fields=['sender', '-created_at']),
            models.Index(fields=['message_type', 'status']),
        ]
    
    def __str__(self):
        return f"{self.subject} ({self.get_message_type_display()})"
    
    def mark_as_read(self):
        """Mark message as read"""
        if self.status in ['sent', 'delivered']:
            self.status = 'read'
            self.read_at = timezone.now()
            self.save(update_fields=['status', 'read_at'])
            return True
        return False
    
    def mark_as_delivered(self):
        """Mark message as delivered"""
        if self.status == 'sent':
            self.status = 'delivered'
            self.delivered_at = timezone.now()
            self.save(update_fields=['status', 'delivered_at'])
            return True
        return False
    
    @property
    def is_unread(self):
        return self.status in ['sent', 'delivered']
    
    @property
    def sender_name(self):
        """Get sender display name"""
        if self.sender:
            return f"{self.sender.first_name} {self.sender.last_name}"
        return "System"
    
    @property
    def receiver_name(self):
        """Get receiver display name"""
        if self.receiver:
            return f"{self.receiver.first_name} {self.receiver.last_name}"
        return "Staff Team"
    
    @property
    def has_replies(self):
        """Check if message has replies"""
        return self.replies.exists()
    
    @property
    def reply_count(self):
        """Count number of replies"""
        return self.replies.count()
    
    def get_conversation_thread(self):
        """Get full conversation thread"""
        if self.parent_message:
            # This is a reply, get the root message
            root = self.parent_message
            while root.parent_message:
                root = root.parent_message
            # Return root and all its replies
            return [root] + list(root.replies.all().order_by('created_at'))
        else:
            # This is the root, return it and all replies
            return [self] + list(self.replies.all().order_by('created_at'))


class MessageTemplate(models.Model):
    """
    Reusable message templates with variable substitution.
    Allows business to create pre-written messages with placeholders.
    """
    TEMPLATE_TYPE_CHOICES = [
        ('welcome', 'Welcome Message'),
        ('thank_you', 'Thank You'),
        ('promotion', 'Promotional Message'),
        ('reminder', 'Reminder'),
        ('birthday', 'Birthday Greeting'),
        ('reward', 'Reward Notification'),
        ('follow_up', 'Follow Up'),
        ('apology', 'Apology'),
        ('custom', 'Custom Template'),
    ]
    
    # Identification
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='message_templates'
    )
    created_by = models.ForeignKey(
        'customers.TenantCustomer',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_templates'
    )
    
    # Template Details
    name = models.CharField(
        max_length=100,
        help_text='Template name for internal reference'
    )
    template_type = models.CharField(
        max_length=20,
        choices=TEMPLATE_TYPE_CHOICES,
        default='custom'
    )
    subject = models.CharField(
        max_length=255,
        help_text='Subject line (supports variables)'
    )
    body = models.TextField(
        help_text='Message body (supports variables like {{customer_name}}, {{points}}, etc.)'
    )
    
    # Usage Statistics
    times_used = models.IntegerField(
        default=0,
        help_text='How many times this template has been used'
    )
    last_used_at = models.DateTimeField(null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'message_templates'
        ordering = ['name']
        verbose_name = 'Message Template'
        verbose_name_plural = 'Message Templates'
        indexes = [
            models.Index(fields=['tenant', 'template_type']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"
    
    def render(self, customer):
        """
        Render template with customer data.
        Replaces variables like {{customer_name}}, {{points}}, etc.
        """
        rendered_subject = self.subject
        rendered_body = self.body
        
        # Replace common variables
        replacements = {
            '{{customer_name}}': f"{customer.first_name} {customer.last_name}",
            '{{first_name}}': customer.first_name,
            '{{last_name}}': customer.last_name,
            '{{email}}': customer.email,
            '{{phone}}': customer.phone or 'N/A',
            '{{points}}': str(customer.loyalty_points),
            '{{business_name}}': customer.tenant.name,
        }
        
        for variable, value in replacements.items():
            rendered_subject = rendered_subject.replace(variable, value)
            rendered_body = rendered_body.replace(variable, value)
        
        return rendered_subject, rendered_body
    
    def increment_usage(self):
        """Increment usage counter"""
        self.times_used += 1
        self.last_used_at = timezone.now()
        self.save(update_fields=['times_used', 'last_used_at'])
    
    @property
    def available_variables(self):
        """List of available variables for this template"""
        return [
            '{{customer_name}}',
            '{{first_name}}',
            '{{last_name}}',
            '{{email}}',
            '{{phone}}',
            '{{points}}',
            '{{business_name}}',
        ]


class MessageAttachment(models.Model):
    """
    Optional: File attachments for messages
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    file = models.FileField(upload_to='message_attachments/%Y/%m/')
    filename = models.CharField(max_length=255)
    file_size = models.IntegerField(help_text='File size in bytes')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'message_attachments'
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.filename} ({self.file_size} bytes)"


