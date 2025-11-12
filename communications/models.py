"""
Communication Models for Ayende CX
Two-way messaging system between customers and businesses
"""

from django.db import models
from django.utils import timezone
import uuid


class Message(models.Model):
    """
    Messages between customers and businesses (two-way communication)
    """
    MESSAGE_TYPE_CHOICES = [
        ('customer_to_business', 'Customer to Business'),
        ('business_to_customer', 'Business to Customer'),
        ('marketing', 'Marketing Campaign'),
        ('notification', 'System Notification'),
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
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='messages')
    
    # Sender and Receiver (flexible for two-way communication)
    sender_customer = models.ForeignKey(
        'customers.TenantCustomer', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='sent_messages',
        help_text='Customer who sent the message'
    )
    receiver_customer = models.ForeignKey(
        'customers.TenantCustomer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='received_messages',
        help_text='Customer who receives the message'
    )
    
    # Message details
    message_type = models.CharField(max_length=30, choices=MESSAGE_TYPE_CHOICES)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')
    
    # Marketing campaign reference
    campaign = models.ForeignKey(
        'MarketingCampaign',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='messages'
    )
    
    # Timestamps
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Thread support (for conversations)
    parent_message = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='replies'
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Message'
        verbose_name_plural = 'Messages'
        indexes = [
            models.Index(fields=['tenant', 'receiver_customer', 'status']),
            models.Index(fields=['tenant', 'sender_customer']),
            models.Index(fields=['message_type', 'status']),
        ]
    
    def __str__(self):
        return f"{self.subject} - {self.get_message_type_display()}"
    
    def mark_as_read(self):
        """Mark message as read"""
        if self.status in ['sent', 'delivered']:
            self.status = 'read'
            self.read_at = timezone.now()
            self.save()
    
    def mark_as_delivered(self):
        """Mark message as delivered"""
        if self.status == 'sent':
            self.status = 'delivered'
            self.delivered_at = timezone.now()
            self.save()
    
    @property
    def is_unread(self):
        return self.status in ['sent', 'delivered']
    
    @property
    def sender_name(self):
        """Get sender display name"""
        if self.sender_customer:
            return f"{self.sender_customer.first_name} {self.sender_customer.last_name}"
        return "Business"
    
    @property
    def receiver_name(self):
        """Get receiver display name"""
        if self.receiver_customer:
            return f"{self.receiver_customer.first_name} {self.receiver_customer.last_name}"
        return "All Customers"


class MarketingCampaign(models.Model):
    """
    Marketing campaigns sent by businesses to customers
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
        ('completed', 'Completed'),
        ('canceled', 'Canceled'),
    ]
    
    TARGET_AUDIENCE_CHOICES = [
        ('all', 'All Customers'),
        ('vip', 'VIP Customers Only'),
        ('high_spenders', 'High Spenders'),
        ('inactive', 'Inactive Customers'),
        ('custom', 'Custom Segment'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='campaigns')
    
    # Campaign details
    name = models.CharField(max_length=255, help_text='Internal campaign name')
    subject = models.CharField(max_length=255, help_text='Message subject line')
    body = models.TextField(help_text='Campaign message content')
    
    # Targeting
    target_audience = models.CharField(max_length=30, choices=TARGET_AUDIENCE_CHOICES, default='all')
    custom_filter = models.JSONField(
        null=True,
        blank=True,
        help_text='Custom audience filter criteria'
    )
    
    # Status and scheduling
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Analytics
    total_recipients = models.IntegerField(default=0)
    total_sent = models.IntegerField(default=0)
    total_delivered = models.IntegerField(default=0)
    total_read = models.IntegerField(default=0)
    
    # Created by
    created_by = models.ForeignKey(
        'customers.TenantCustomer',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_campaigns'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Marketing Campaign'
        verbose_name_plural = 'Marketing Campaigns'
    
    def __str__(self):
        return f"{self.name} - {self.get_status_display()}"
    
    def get_target_customers(self):
        """Get customers based on target audience"""
        from customers.models import TenantCustomer, Transaction
        
        customers = TenantCustomer.objects.filter(
            tenant=self.tenant,
            role='customer',
            is_active=True
        )
        
        if self.target_audience == 'vip':
            customers = customers.filter(is_vip=True)
        elif self.target_audience == 'high_spenders':
            customers = customers.filter(total_spent__gte=1000)
        elif self.target_audience == 'inactive':
            # Customers with no transactions in last 30 days
            thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
            active_customer_ids = Transaction.objects.filter(
                tenant=self.tenant,
                transaction_date__gte=thirty_days_ago
            ).values_list('tenant_customer_id', flat=True).distinct()
            customers = customers.exclude(id__in=active_customer_ids)
        elif self.target_audience == 'custom' and self.custom_filter:
            # Apply custom filters
            pass  # Implement based on custom_filter JSON
        
        return customers
    
    def send_campaign(self):
        """Send campaign to all target customers"""
        if self.status != 'draft':
            return False
        
        customers = self.get_target_customers()
        self.total_recipients = customers.count()
        self.status = 'sending'
        self.sent_at = timezone.now()
        self.save()
        
        # Create messages for each customer
        messages_created = 0
        for customer in customers:
            message = Message.objects.create(
                tenant=self.tenant,
                receiver_customer=customer,
                message_type='marketing',
                subject=self.subject,
                body=self.body,
                status='sent',
                campaign=self,
                sent_at=timezone.now()
            )
            messages_created += 1
            
            # Send email notification
            self._send_email_notification(message, customer)
        
        self.total_sent = messages_created
        self.status = 'sent'
        self.completed_at = timezone.now()
        self.save()
        
        return True
    
    def _send_email_notification(self, message, customer):
        """Send email notification (implement with SendGrid)"""
        # TODO: Implement email sending via SendGrid
        pass
    
    @property
    def open_rate(self):
        """Calculate campaign open rate"""
        if self.total_delivered > 0:
            return (self.total_read / self.total_delivered) * 100
        return 0
    
    @property
    def delivery_rate(self):
        """Calculate delivery rate"""
        if self.total_sent > 0:
            return (self.total_delivered / self.total_sent) * 100
        return 0


class Notification(models.Model):
    """
    System notifications for customers (in-app alerts)
    """
    NOTIFICATION_TYPE_CHOICES = [
        ('message', 'New Message'),
        ('reward', 'Reward Available'),
        ('points', 'Loyalty Points Update'),
        ('promotion', 'Special Promotion'),
        ('order', 'Order Update'),
        ('system', 'System Notification'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='communication_notifications')
    customer = models.ForeignKey(
        'customers.TenantCustomer',
        on_delete=models.CASCADE,
        related_name='communication_notifications'
    )
    
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPE_CHOICES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    
    # Status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Link (optional)
    link_url = models.CharField(max_length=500, blank=True, help_text='Optional link to related content')
    
    # Related objects
    related_message = models.ForeignKey(
        Message,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='message_notifications'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        indexes = [
            models.Index(fields=['customer', 'is_read']),
            models.Index(fields=['tenant', 'notification_type']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.customer}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()
    
    @classmethod
    def create_for_message(cls, message):
        """Create notification when customer receives a message"""
        if message.receiver_customer:
            return cls.objects.create(
                tenant=message.tenant,
                customer=message.receiver_customer,
                notification_type='message',
                title='New Message',
                message=f"You have a new message: {message.subject}",
                related_message=message,
                link_url=f'/messages/{message.id}/'
            )
        return None
    
    @classmethod
    def create_for_reward(cls, customer, reward):
        """Create notification when customer earns a reward"""
        return cls.objects.create(
            tenant=customer.tenant,
            customer=customer,
            notification_type='reward',
            title='Reward Available!',
            message=f"You've earned a reward: {reward.name}",
            link_url='/rewards/'
        )
    
    @classmethod
    def create_for_points(cls, customer, points_earned):
        """Create notification for loyalty points update"""
        return cls.objects.create(
            tenant=customer.tenant,
            customer=customer,
            notification_type='points',
            title='Loyalty Points Update',
            message=f"You've earned {points_earned} loyalty points!",
            link_url='/loyalty/'
        )


class MessageTemplate(models.Model):
    """
    Reusable message templates for businesses
    """
    TEMPLATE_TYPE_CHOICES = [
        ('welcome', 'Welcome Message'),
        ('promotion', 'Promotional Message'),
        ('reminder', 'Reminder'),
        ('thank_you', 'Thank You'),
        ('birthday', 'Birthday Greeting'),
        ('custom', 'Custom Template'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='message_templates')
    
    name = models.CharField(max_length=255)
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPE_CHOICES)
    subject = models.CharField(max_length=255)
    body = models.TextField(help_text='Use {{customer_name}}, {{points}}, etc. for variables')
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Message Template'
        verbose_name_plural = 'Message Templates'
    
    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"
    
    def render(self, customer):
        """Render template with customer data"""
        body = self.body
        body = body.replace('{{customer_name}}', f"{customer.first_name} {customer.last_name}")
        body = body.replace('{{first_name}}', customer.first_name)
        body = body.replace('{{points}}', str(customer.loyalty_points))
        body = body.replace('{{email}}', customer.email)
        return body