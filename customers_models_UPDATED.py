"""
Customer Models - Ayende CX (Multi-Tenant Version)
Customers are now scoped to specific tenants (businesses)
"""

from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils import timezone


class CustomerManager(BaseUserManager):
    """Custom manager for Customer model - platform level"""
    
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        
        email = self.normalize_email(email)
        extra_fields.setdefault('username', email)
        
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


class Customer(AbstractUser):
    """
    Customer model with authentication and profile - PLATFORM LEVEL
    Customers can have relationships with MULTIPLE businesses (tenants)
    """
    
    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('fr', 'French'),
    ]
    
    # NO tenant FK - customers are platform-level
    # Relationships to tenants managed via TenantCustomer model
    
    # Authentication
    email = models.EmailField(unique=True)  # Email is globally unique
    username = models.CharField(max_length=150, unique=True)
    
    # Personal Information
    phone = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    
    # Address
    street_address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    province = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, default='Canada')
    
    # Preferences
    preferred_language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default='en')
    dietary_preferences = models.TextField(blank=True)
    favorite_products = models.TextField(blank=True)
    
    # Loyalty & Marketing
    loyalty_points = models.IntegerField(default=0)
    total_purchases = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    last_purchase_date = models.DateField(null=True, blank=True)
    
    # Notifications
    email_notifications = models.BooleanField(default=False)
    sms_notifications = models.BooleanField(default=False)
    push_notifications = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = CustomerManager()
    
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email', 'first_name', 'last_name']
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'
        # No tenant-based unique constraints - customers are global
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"
    
    @property
    def full_name(self):
        return self.get_full_name()
    
    def get_tenant_relationships(self):
        """Get all business relationships for this customer"""
        return TenantCustomer.objects.filter(customer=self).select_related('tenant')
    
    def is_customer_of(self, tenant):
        """Check if customer has relationship with specific tenant"""
        return TenantCustomer.objects.filter(
            customer=self,
            tenant=tenant,
            is_active=True
        ).exists()


class TenantCustomer(models.Model):
    """
    Junction table linking Customers to Tenants with relationship data.
    This is where tenant-specific customer data lives.
    
    Example: John is a customer of both Simi Food and Afro Shop
    - TenantCustomer(customer=John, tenant=Simi Food, loyalty_points=500)
    - TenantCustomer(customer=John, tenant=Afro Shop, loyalty_points=200)
    """
    
    # The Relationship
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='tenant_relationships'
    )
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='customer_relationships'
    )
    
    # Tenant-Specific Customer Data
    loyalty_points = models.IntegerField(default=0)
    total_purchases = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    last_purchase_date = models.DateField(null=True, blank=True)
    
    # Tenant-Specific Preferences
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    push_notifications = models.BooleanField(default=True)
    
    # Tenant-Specific Notes
    internal_notes = models.TextField(
        blank=True,
        help_text="Staff notes about this customer (not visible to customer)"
    )
    
    # Customer Status within this Tenant
    is_active = models.BooleanField(default=True)
    is_vip = models.BooleanField(default=False)
    
    # Relationship Metadata
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'tenant_customers'
        unique_together = [['customer', 'tenant']]
        ordering = ['-joined_at']
        verbose_name = 'Customer-Business Relationship'
        verbose_name_plural = 'Customer-Business Relationships'
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['customer', 'tenant']),
        ]
    
    def __str__(self):
        return f"{self.customer.email} → {self.tenant.name}"


class CustomerGroup(models.Model):
    """
    Customer Groups for segmentation and targeted marketing
    Groups are tenant-specific
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='customer_groups'
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Now references TenantCustomer relationships, not Customers directly
    customer_relationships = models.ManyToManyField(
        TenantCustomer,
        related_name='groups',
        blank=True
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Customer Group'
        verbose_name_plural = 'Customer Groups'
        unique_together = [['tenant', 'name']]
    
    def __str__(self):
        return f"{self.tenant.name} - {self.name}"
    
    def customer_count(self):
        """Return number of customer relationships in group"""
        return self.customer_relationships.filter(is_active=True).count()


class CustomerNote(models.Model):
    """
    Staff notes about customers - scoped to tenant relationship
    """
    tenant_customer = models.ForeignKey(
        TenantCustomer,
        on_delete=models.CASCADE,
        related_name='notes'
    )
    note = models.TextField()
    created_by = models.ForeignKey(
        Customer, 
        on_delete=models.SET_NULL, 
        null=True,
        blank=True,
        related_name='created_notes'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Note for {self.tenant_customer.customer.email} at {self.tenant_customer.tenant.name}"


class Notification(models.Model):
    """
    System notifications and promotions - tenant-scoped
    Sent to customers within context of their relationship with a tenant
    """
    
    NOTIFICATION_TYPES = [
        ('promotion', 'Promotion'),
        ('announcement', 'Announcement'),
        ('birthday', 'Birthday Greeting'),
        ('account', 'Account Update'),
        ('system', 'System Message'),
    ]
    
    # Tenant scope
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='notifications',
        help_text='Business sending this notification'
    )
    
    # Target - uses TenantCustomer relationship
    tenant_customer = models.ForeignKey(
        TenantCustomer,
        on_delete=models.CASCADE,
        related_name='notifications',
        null=True,
        blank=True,
        help_text='Specific customer relationship to notify'
    )
    
    group = models.ForeignKey(
        CustomerGroup,
        on_delete=models.CASCADE,
        related_name='notifications',
        null=True,
        blank=True,
        help_text='Send to specific customer group'
    )
    
    # Content
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPES,
        default='announcement'
    )
    
    # Status
    is_read = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        indexes = [
            models.Index(fields=['tenant', 'tenant_customer', 'is_read']),
        ]
    
    def __str__(self):
        if self.tenant_customer:
            return f"{self.tenant.name} - {self.title} - {self.tenant_customer.customer.email}"
        elif self.group:
            return f"{self.tenant.name} - {self.title} - Group: {self.group.name}"
        return f"{self.tenant.name} - {self.title} - All Customers"
    
    def send_to_group_members(self):
        """Create individual notifications for all group members"""
        if not self.group:
            return 0
        
        count = 0
        for relationship in self.group.customer_relationships.filter(is_active=True):
            Notification.objects.create(
                tenant=self.tenant,
                tenant_customer=relationship,
                title=self.title,
                message=self.message,
                notification_type=self.notification_type,
                is_active=self.is_active,
                expires_at=self.expires_at
            )
            count += 1
        
        return count
    
    def send_to_all_customers(self):
        """Create individual notifications for all customers in tenant"""
        count = 0
        for relationship in self.tenant.customer_relationships.filter(is_active=True):
            Notification.objects.create(
                tenant=self.tenant,
                tenant_customer=relationship,
                title=self.title,
                message=self.message,
                notification_type=self.notification_type,
                is_active=self.is_active,
                expires_at=self.expires_at
            )
            count += 1
        
        return count
