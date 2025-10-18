"""
Tenant Models for Ayende CRMForce
Multi-tenant SaaS platform for local businesses
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from django.core.validators import RegexValidator
import uuid


class Tenant(models.Model):
    """
    Represents a business/organization using the platform.
    Each tenant has complete data isolation.
    """
    
    SUBSCRIPTION_STATUS = [
        ('trial', 'Trial'),
        ('active', 'Active'),
        ('past_due', 'Past Due'),
        ('cancelled', 'Cancelled'),
        ('suspended', 'Suspended'),
    ]
    
    # Identification
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, help_text="Business name")
    slug = models.SlugField(
        unique=True, 
        max_length=100, 
        help_text="URL-friendly name for subdomain (e.g., 'simifood' for simifood.ayendecrm.com)",
        validators=[
            RegexValidator(
                regex='^[a-z0-9-]+$',
                message='Slug can only contain lowercase letters, numbers, and hyphens'
            )
        ]
    )
    
    # Business Information
    business_email = models.EmailField()
    business_phone = models.CharField(max_length=20, blank=True)
    business_address = models.TextField(blank=True)
    website = models.URLField(blank=True)
    description = models.TextField(blank=True, help_text="Brief description of the business")
    
    # Branding
    logo = models.ImageField(upload_to='tenant_logos/', blank=True, null=True)
    primary_color = models.CharField(
        max_length=7, 
        default='#228B22', 
        help_text="Hex color code for primary brand color"
    )
    secondary_color = models.CharField(
        max_length=7, 
        default='#FF8C00', 
        help_text="Hex color code for secondary brand color"
    )
    
    # Subscription & Limits
    subscription_status = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_STATUS,
        default='trial'
    )
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    subscription_starts_at = models.DateTimeField(null=True, blank=True)
    subscription_ends_at = models.DateTimeField(null=True, blank=True)
    
    # Usage Limits (will be tied to subscription plans later)
    max_customers = models.IntegerField(
        default=100,
        help_text="Maximum number of customers allowed"
    )
    max_storage_gb = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=5.0,
        help_text="Maximum storage in GB"
    )
    max_users = models.IntegerField(
        default=3,
        help_text="Maximum number of staff users"
    )
    
    # Ownership
    owner = models.ForeignKey(
        'customers.Customer',
        on_delete=models.PROTECT,
        related_name='owned_tenants',
        help_text="Primary business owner/admin"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'tenants'
        ordering = ['-created_at']
        verbose_name = 'Business Tenant'
        verbose_name_plural = 'Business Tenants'
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['subscription_status']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        # Auto-generate slug from name if not provided
        if not self.slug:
            self.slug = slugify(self.name)
        
        # Ensure slug is lowercase
        self.slug = self.slug.lower()
        
        super().save(*args, **kwargs)
    
    @property
    def subdomain_url(self):
        """Returns the full subdomain URL for this tenant"""
        from django.conf import settings
        domain = settings.CUSTOM_DOMAIN or 'ayendecrm.com'
        return f"https://{self.slug}.{domain}"
    
    @property
    def is_trial(self):
        """Check if tenant is in trial period"""
        return self.subscription_status == 'trial'
    
    @property
    def is_subscribed(self):
        """Check if tenant has an active subscription"""
        return self.subscription_status == 'active'
    
    @property
    def customer_count(self):
        """Get current number of customers"""
        return self.tenant_customers.count()
    
    @property
    def can_add_customers(self):
        """Check if tenant can add more customers"""
        return self.customer_count < self.max_customers
    
    def get_admin_url(self):
        """Returns the admin URL for this tenant"""
        return f"{self.subdomain_url}/admin/"


class TenantSettings(models.Model):
    """
    Additional settings for each tenant
    Separated from main Tenant model for flexibility
    """
    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name='settings'
    )
    
    # Notification Settings
    enable_email_notifications = models.BooleanField(default=True)
    enable_push_notifications = models.BooleanField(default=True)
    enable_sms_notifications = models.BooleanField(default=False)
    
    # Customer Settings
    allow_customer_registration = models.BooleanField(
        default=True,
        help_text="Allow customers to register themselves"
    )
    require_email_verification = models.BooleanField(default=True)
    loyalty_points_enabled = models.BooleanField(default=True)
    
    # Business Hours
    business_hours = models.JSONField(
        default=dict,
        blank=True,
        help_text="Store business hours in JSON format"
    )
    
    # Custom fields for customer data
    custom_fields = models.JSONField(
        default=dict,
        blank=True,
        help_text="Custom fields to collect from customers"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'tenant_settings'
        verbose_name = 'Tenant Settings'
        verbose_name_plural = 'Tenant Settings'
    
    def __str__(self):
        return f"Settings for {self.tenant.name}"