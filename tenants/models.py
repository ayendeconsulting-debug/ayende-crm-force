"""
Tenants Models - Fixed with subscription_status and subdomain fields
Added tenant_uuid with pattern a-cx-{Random-5}
"""

from django.db import models
from django.utils import timezone
from django.core.validators import RegexValidator
import random
import string


# DON'T import Customer directly - use string reference to avoid circular imports


def generate_tenant_uuid():
    """
    Generate unique tenant UUID with pattern: a-cx-{5 random alphanumeric}
    Example: a-cx-3k9f2, a-cx-x7m4q
    """
    characters = string.ascii_lowercase + string.digits
    random_part = ''.join(random.choices(characters, k=5))
    return f'a-cx-{random_part}'


class Tenant(models.Model):
    """
    Multi-tenant business model
    Each business is a separate tenant with its own subdomain
    """
    
    # Unique Identifier (NEW)
    tenant_uuid = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        default=generate_tenant_uuid,
        db_index=True,
        help_text='Unique tenant identifier (e.g., a-cx-3k9f2)'
    )
    
    # Basic Information
    name = models.CharField(
        max_length=200,
        help_text='Business name'
    )
    
    slug = models.SlugField(
        max_length=50,
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^[a-z0-9-]+$',
                message='Slug can only contain lowercase letters, numbers, and hyphens'
            )
        ],
        help_text='URL-friendly name for subdomain (e.g., "simifood" for simifood.localhost:8000)'
    )
    
    subdomain = models.CharField(
        max_length=63,
        unique=True,
        db_index=True,
        validators=[
            RegexValidator(
                regex=r'^[a-z0-9-]+$',
                message='Subdomain can only contain lowercase letters, numbers, and hyphens'
            )
        ],
        help_text='Subdomain for tenant (e.g., "simifood" for simifood.ayendecx.com)'
    )
    
    description = models.TextField(
        blank=True,
        help_text='Brief description of the business'
    )
    
    # FIXED: Use string reference instead of direct import
    owner = models.ForeignKey(
        'customers.Customer',  # String reference - no import needed!
        on_delete=models.CASCADE,
        related_name='owned_tenants',
        help_text='Business owner'
    )
    
    # Regional Settings
    CURRENCY_CHOICES = [
        ('USD', 'US Dollar ($)'),
        ('CAD', 'Canadian Dollar (C$)'),
        ('GBP', 'British Pound (£)'),
        ('EUR', 'Euro (€)'),
        ('AUD', 'Australian Dollar (A$)'),
        ('NGN', 'Nigerian Naira (₦)'),
        ('ZAR', 'South African Rand (R)'),
        ('KES', 'Kenyan Shilling (KSh)'),
        ('GHS', 'Ghanaian Cedi (GH₵)'),
        ('UGX', 'Ugandan Shilling (USh)'),
        ('TZS', 'Tanzanian Shilling (TSh)'),
        ('EGP', 'Egyptian Pound (E£)'),
        ('MAD', 'Moroccan Dirham (DH)'),
        ('JPY', 'Japanese Yen (¥)'),
        ('CNY', 'Chinese Yuan (¥)'),
        ('INR', 'Indian Rupee (₹)'),
        ('CHF', 'Swiss Franc (CHF)'),
    ]
    
    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default='USD',
        help_text='Currency for this business'
    )
    
    currency_symbol = models.CharField(
        max_length=10,
        default='$',
        help_text='Currency symbol to display (e.g., $, £, ₦, €)'
    )
    
    CURRENCY_POSITION_CHOICES = [
        ('before', 'Before amount ($100)'),
        ('after', 'After amount (100$)'),
    ]
    
    currency_position = models.CharField(
        max_length=10,
        choices=CURRENCY_POSITION_CHOICES,
        default='before',
        help_text='Where to display currency symbol'
    )
    
    decimal_places = models.IntegerField(
        default=2,
        help_text='Number of decimal places for currency'
    )
    
    # Branding
    logo = models.ImageField(
        upload_to='tenant_logos/',
        blank=True,
        null=True,
        help_text='Business logo'
    )
    
    primary_color = models.CharField(
        max_length=7,
        default='#228B22',
        help_text='Hex color code for primary brand color (e.g., #228B22)'
    )
    
    secondary_color = models.CharField(
        max_length=7,
        default='#FF8C00',
        help_text='Hex color code for secondary brand color'
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text='Whether this business is active'
    )
    
    # Subscription Status
    SUBSCRIPTION_STATUS_CHOICES = [
        ('trial', 'Trial'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
        ('cancelled', 'Cancelled'),
    ]
    
    subscription_status = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_STATUS_CHOICES,
        default='trial',
        help_text='Current subscription status'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Business Tenant'
        verbose_name_plural = 'Business Tenants'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.tenant_uuid})"
    
    def save(self, *args, **kwargs):
        """
        Override save to ensure tenant_uuid is generated if not present
        """
        if not self.tenant_uuid:
            # Generate UUID and ensure it's unique
            while True:
                new_uuid = generate_tenant_uuid()
                if not Tenant.objects.filter(tenant_uuid=new_uuid).exists():
                    self.tenant_uuid = new_uuid
                    break
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        """Return the tenant's URL"""
        return f"http://{self.subdomain}.localhost:8000/"


class TenantSettings(models.Model):
    """
    Configuration settings for each tenant
    """
    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name='settings',
        primary_key=True
    )
    
    # Registration Settings
    allow_customer_registration = models.BooleanField(
        default=True,
        help_text='Allow customers to self-register'
    )
    
    require_email_verification = models.BooleanField(
        default=False,
        help_text='Require email verification for new customers'
    )
    
    # Limits
    max_customers = models.IntegerField(
        default=1000,
        help_text='Maximum number of customers allowed'
    )
    
    max_staff_members = models.IntegerField(
        default=10,
        help_text='Maximum number of staff members'
    )
    
    # Loyalty Program
    enable_loyalty_points = models.BooleanField(
        default=True,
        help_text='Enable loyalty points system'
    )
    
    points_per_dollar = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=1.00,
        help_text='Points earned per dollar spent'
    )
    
    # Notifications
    enable_email_notifications = models.BooleanField(default=True)
    enable_sms_notifications = models.BooleanField(default=False)
    
    # Business Hours
    business_hours = models.JSONField(
        default=dict,
        blank=True,
        help_text='Business operating hours'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Tenant Settings"
        verbose_name_plural = "Tenant Settings"
    
    def __str__(self):
        return f"{self.tenant.name} - Settings"