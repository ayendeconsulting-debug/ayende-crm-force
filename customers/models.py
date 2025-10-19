"""
Customer Models for Ayende CX
Custom user model with multi-tenant support
"""

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.core.validators import RegexValidator
import uuid
from django.utils import timezone

class CustomerManager(BaseUserManager):
    """
    Custom manager for Customer model
    """
    
    def create_user(self, email, password=None, **extra_fields):
        """Create and return a regular user"""
        if not email:
            raise ValueError('Email address is required')
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        """Create and return a superuser"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True')
        
        return self.create_user(email, password, **extra_fields)


class Customer(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model for customers.
    Can belong to multiple tenants (businesses).
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Authentication
    email = models.EmailField(unique=True, max_length=255)
    
    # Personal Information
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(
        max_length=20,
        blank=True,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message="Phone number must be in format: '+999999999'. Up to 15 digits allowed."
            )
        ]
    )
    
    # Profile
    profile_picture = models.ImageField(
        upload_to='customer_profiles/',
        blank=True,
        null=True
    )
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, blank=True, default='Canada')
    
    # Permissions
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    
    # Preferences
    preferred_language = models.CharField(
        max_length=10,
        default='en',
        choices=[
            ('en', 'English'),
            ('fr', 'French'),
        ]
    )
    
    # Timestamps
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Many-to-Many relationship with Tenants through TenantCustomer
    tenants = models.ManyToManyField(
        'tenants.Tenant',
        through='TenantCustomer',
        related_name='customers'
    )
    
    objects = CustomerManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    class Meta:
        db_table = 'customers'
        ordering = ['-date_joined']
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['last_name', 'first_name']),
        ]
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"
    
    def get_full_name(self):
        """Return the full name"""
        return f"{self.first_name} {self.last_name}".strip()
    
    def get_short_name(self):
        """Return the short name (first name)"""
        return self.first_name
    
    @property
    def initials(self):
        """Get user initials for avatar"""
        return f"{self.first_name[0]}{self.last_name[0]}".upper() if self.first_name and self.last_name else "?"


class TenantCustomer(models.Model):
    """
    Through model linking Customers to Tenants.
    Stores tenant-specific customer data like loyalty points, preferences, etc.
    """
    
    ROLE_CHOICES = [
        ('owner', 'Owner'),          # Business owner
        ('admin', 'Administrator'),   # Full admin access
        ('manager', 'Manager'),       # Can manage customers and content
        ('staff', 'Staff'),          # Limited access
        ('customer', 'Customer'),     # Regular customer
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='tenant_relationships'
    )
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='tenant_customers'
    )
    
    # Role & Permissions
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='customer'
    )
    
    # Customer-specific data for this tenant
    loyalty_points = models.IntegerField(default=0)
    total_purchases = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )
    loyalty_points = models.IntegerField(default=0)
    total_purchases = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_spent = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)  # ADD THIS LINE
    last_purchase_date = models.DateField(null=True, blank=True)

    purchase_count = models.IntegerField(default=0)
    
    # Preferences
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    push_notifications = models.BooleanField(default=True)
    
    # Customer notes (visible to business staff only)
    notes = models.TextField(blank=True, help_text="Internal notes about this customer")
    
    
    # Tags for segmentation
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Tags for customer segmentation (e.g., ['vip', 'frequent'])"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    is_vip = models.BooleanField(default=False)
    
    # Timestamps
    joined_at = models.DateTimeField(auto_now_add=True)
    last_purchase_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'tenant_customers'
        unique_together = ['customer', 'tenant']
        ordering = ['-joined_at']
        verbose_name = 'Tenant-Customer Relationship'
        verbose_name_plural = 'Tenant-Customer Relationships'
        indexes = [
            models.Index(fields=['tenant', 'role']),
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['loyalty_points']),
        ]
    
    def __str__(self):
        return f"{self.customer.get_full_name()} at {self.tenant.name}"
    
    @property
    def is_staff_member(self):
        """Check if this customer is a staff member (not a regular customer)"""
        return self.role in ['owner', 'admin', 'manager', 'staff']
    
    @property
    def is_business_owner(self):
        """Check if this customer is the business owner"""
        return self.role == 'owner'
    
    def add_loyalty_points(self, points):
        """Add loyalty points"""
        self.loyalty_points += points
        self.save(update_fields=['loyalty_points', 'updated_at'])
    
    def redeem_loyalty_points(self, points):
        """Redeem loyalty points"""
        if self.loyalty_points >= points:
            self.loyalty_points -= points
            self.save(update_fields=['loyalty_points', 'updated_at'])
            return True
        return False
    
    def record_purchase(self, amount):
        """Record a purchase"""
        from django.utils import timezone
        self.total_purchases += amount
        self.purchase_count += 1
        self.last_purchase_at = timezone.now()
        self.save(update_fields=['total_purchases', 'purchase_count', 'last_purchase_at', 'updated_at'])
class Transaction(models.Model):
    """
    Track customer transactions/purchases per tenant.
    Each purchase is recorded here with details.
    """
    
    TRANSACTION_TYPE_CHOICES = [
        ('purchase', 'Purchase'),
        ('refund', 'Refund'),
        ('adjustment', 'Points Adjustment'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('card', 'Credit/Debit Card'),
        ('mobile', 'Mobile Payment'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('completed', 'Completed'),
        ('pending', 'Pending'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]
    
    # Relationships
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    tenant_customer = models.ForeignKey(
        TenantCustomer,
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    
    # Transaction Details
    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPE_CHOICES,
        default='purchase'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='completed'
    )
    
    # Financial Information
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Transaction amount"
    )
    tax = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Tax amount"
    )
    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Total amount (amount + tax)"
    )
    
    # Payment
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='cash'
    )
    
    # Loyalty Points
    points_earned = models.IntegerField(
        default=0,
        help_text="Loyalty points earned from this transaction"
    )
    points_redeemed = models.IntegerField(
        default=0,
        help_text="Loyalty points used in this transaction"
    )
    
    # Transaction Metadata
    transaction_id = models.CharField(
        max_length=100,
        unique=True,
        blank=True,
        help_text="Unique transaction identifier"
    )
    receipt_number = models.CharField(max_length=50, blank=True)
    items_description = models.TextField(
        blank=True,
        help_text="Brief description of items purchased"
    )
    notes = models.TextField(blank=True)
    
    # Timestamps
    transaction_date = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Staff who processed transaction
    processed_by = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_transactions',
        help_text="Staff member who processed this transaction"
    )
    
    class Meta:
        db_table = 'transactions'
        ordering = ['-transaction_date']
        indexes = [
            models.Index(fields=['tenant', 'customer', '-transaction_date']),
            models.Index(fields=['tenant', '-transaction_date']),
            models.Index(fields=['transaction_id']),
            models.Index(fields=['status']),
        ]
        verbose_name = 'Transaction'
        verbose_name_plural = 'Transactions'
    
    def __str__(self):
        return f"Transaction {self.transaction_id or self.id} - {self.customer.email} - ${self.total}"
    
    def save(self, *args, **kwargs):
        # Auto-generate transaction ID if not provided
        if not self.transaction_id:
            import uuid
            self.transaction_id = f"TXN-{uuid.uuid4().hex[:12].upper()}"
        
        # Calculate total if not provided
        if not self.total:
            self.total = self.amount + self.tax
        
        # Auto-calculate loyalty points earned (1 point per dollar spent)
        if self.transaction_type == 'purchase' and self.status == 'completed':
            if not self.points_earned:
                self.points_earned = int(self.total)
        
        super().save(*args, **kwargs)
        
        # Update customer stats after saving
        if self.status == 'completed':
            self.update_customer_stats()
    
    def update_customer_stats(self):
        """Update TenantCustomer statistics after transaction"""
        if self.transaction_type == 'purchase':
            # Update loyalty points
            self.tenant_customer.loyalty_points += self.points_earned
            self.tenant_customer.loyalty_points -= self.points_redeemed
            
            # Update total spent
            if not hasattr(self.tenant_customer, 'total_spent'):
                # If field doesn't exist yet, track in total_purchases
                self.tenant_customer.total_purchases += self.total
            else:
                self.tenant_customer.total_spent += self.total
            
            # Update last purchase date
            self.tenant_customer.last_purchase_date = self.transaction_date.date()
            
            self.tenant_customer.save()
    
    @property
    def is_refundable(self):
        """Check if transaction can be refunded"""
        return self.status == 'completed' and self.transaction_type == 'purchase'
    
    @property
    def display_status(self):
        """Get display-friendly status"""
        status_colors = {
            'completed': '✅',
            'pending': '⏳',
            'cancelled': '❌',
            'refunded': '↩️',
        }
        return f"{status_colors.get(self.status, '')} {self.get_status_display()}"
