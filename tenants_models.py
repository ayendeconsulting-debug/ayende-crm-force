"""
Tenant Models for Ayende CRMForce
Multi-tenant SaaS platform for local businesses
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils.text import slugify
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
    slug = models.SlugField(unique=True, max_length=100, help_text="URL-friendly name for subdomain")
    
    # Business Information
    business_email = models.EmailField()
    business_phone = models.CharField(max_length=20, blank=True)
    business_address = models.TextField(blank=True)
    website = models.URLField(blank=True)
    
    # Branding
    logo = models.ImageField(upload_to='tenant_logos/', blank=True, null=True)
    primary_color = models.CharField(max_length=7, default='#228B22', help_text="Hex color code")
    secondary_color = models.CharField(max_length=7, default='#FF8C00', help_text="Hex color code")
    
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
    max_customers = models.IntegerField(default=100)
    max_storage_gb = models.DecimalField(max_digits=10, decimal_places=2, default=5.0)
    max_users = models.IntegerField(default=3)
    
    # Ownership
    owner = models.ForeignKey(
        get_user_model(),
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
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        # Auto-generate slug from name if not provided
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    @property
    def subdomain_url(self):
        """Generate subdomain URL for tenant"""
        return f"https://{self.slug}.ayendecrm.com"
    
    @property
    def is_trial(self):
        """Check if tenant is in trial period"""
        if self.subscription_status == 'trial' and self.trial_ends_at:
            from django.utils import timezone
            return timezone.now() < self.trial_ends_at
        return False
    
    @property
    def days_until_trial_ends(self):
        """Calculate days remaining in trial"""
        if self.is_trial:
            from django.utils import timezone
            delta = self.trial_ends_at - timezone.now()
            return max(0, delta.days)
        return 0
    
    @property
    def customer_count(self):
        """Get current customer count via relationships"""
        return self.customer_relationships.filter(is_active=True).count()
    
    @property
    def is_at_customer_limit(self):
        """Check if tenant has reached customer limit"""
        return self.customer_count >= self.max_customers


class TenantUser(models.Model):
    """
    Links users (staff members) to tenants with specific roles.
    These are business employees, NOT customers.
    """
    
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('admin', 'Administrator'),
        ('manager', 'Manager'),
        ('staff', 'Staff'),
    ]
    
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='tenant_users'
    )
    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name='tenant_memberships'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='staff')
    
    # Permissions
    can_manage_customers = models.BooleanField(default=False)
    can_send_notifications = models.BooleanField(default=False)
    can_view_reports = models.BooleanField(default=True)
    can_manage_settings = models.BooleanField(default=False)
    can_manage_users = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'tenant_users'
        unique_together = ['tenant', 'user']
        verbose_name = 'Tenant User'
        verbose_name_plural = 'Tenant Users'
    
    def __str__(self):
        return f"{self.user.email} - {self.tenant.name} ({self.role})"
    
    def save(self, *args, **kwargs):
        # Auto-grant permissions based on role
        if self.role == 'owner':
            self.can_manage_customers = True
            self.can_send_notifications = True
            self.can_view_reports = True
            self.can_manage_settings = True
            self.can_manage_users = True
        elif self.role == 'admin':
            self.can_manage_customers = True
            self.can_send_notifications = True
            self.can_view_reports = True
            self.can_manage_settings = True
            self.can_manage_users = False
        elif self.role == 'manager':
            self.can_manage_customers = True
            self.can_send_notifications = True
            self.can_view_reports = True
            self.can_manage_settings = False
            self.can_manage_users = False
        
        super().save(*args, **kwargs)
