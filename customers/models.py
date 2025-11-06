"""
Customer Models for Ayende CX
Custom user model with multi-tenant support and email verification
UPDATED: Integration fields added for POS sync
"""

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.core.validators import RegexValidator
import uuid
import secrets
from django.utils import timezone
from datetime import timedelta

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
        extra_fields.setdefault('email_verified', True)  # Auto-verify superusers
        
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
    state = models.CharField(max_length=100, blank=True)  # 🔗 INTEGRATION: Added for POS sync
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
    
    # Email Verification
    email_verified = models.BooleanField(
        default=False,
        help_text='Whether the email address has been verified'
    )
    
    email_verification_token = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        unique=True,
        help_text='Token for email verification'
    )
    
    email_verification_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When the verification email was last sent'
    )
    
      # Loyalty program
    loyalty_points = models.IntegerField(default=0)
    loyalty_tier = models.CharField(max_length=20, default='BRONZE', 
                                     choices=[('BRONZE','Bronze'),('SILVER','Silver'),
                                             ('GOLD','Gold'),('PLATINUM','Platinum')])
    total_spent = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    visit_count = models.IntegerField(default=0)
    last_visit = models.DateTimeField(null=True, blank=True)  # 🔗 INTEGRATION: Last transaction date
    marketing_opt_in = models.BooleanField(default=False)
    needs_enrichment = models.BooleanField(default=False)
    
    # ============================================
    # 🔗 INTEGRATION: POS sync fields
    # ============================================
    external_id = models.UUIDField(
        unique=True,
        null=True,
        blank=True,
        help_text='Customer ID from POS system',
        db_index=True
    )
    
    last_synced_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Last time data was synced from POS'
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
            models.Index(fields=['email_verification_token']),
            models.Index(fields=['external_id']),  # 🔗 INTEGRATION INDEX
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
    
    @property
    def zip_code(self):
        """Alias for postal_code for POS sync compatibility"""
        return self.postal_code
    
    @zip_code.setter
    def zip_code(self, value):
        """Allow setting zip_code which updates postal_code"""
        self.postal_code = value
    
    def generate_verification_token(self):
        """Generate a unique verification token"""
        self.email_verification_token = secrets.token_urlsafe(32)
        self.email_verification_sent_at = timezone.now()
        self.save(update_fields=['email_verification_token', 'email_verification_sent_at'])
        return self.email_verification_token
    
    def is_verification_token_valid(self):
        """Check if verification token is still valid (24 hours)"""
        if not self.email_verification_sent_at:
            return False
        
        expiry_time = self.email_verification_sent_at + timedelta(hours=24)
        return timezone.now() < expiry_time
    
    def verify_email(self):
        """Mark email as verified"""
        self.email_verified = True
        self.email_verification_token = None
        self.email_verification_sent_at = None
        self.save(update_fields=['email_verified', 'email_verification_token', 'email_verification_sent_at'])


class TenantCustomer(models.Model):
    """
    Through model linking Customers to Tenants.
    Stores tenant-specific customer data like loyalty points, preferences, etc.
    """
    
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('admin', 'Administrator'),
        ('manager', 'Manager'),
        ('staff', 'Staff'),
        ('customer', 'Customer'),
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
    total_purchases = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_spent = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    last_purchase_date = models.DateField(null=True, blank=True)
    purchase_count = models.IntegerField(default=0)
    
    # Preferences - NOTIFICATION FIELDS
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
    
    # VIP Status (auto-calculated based on tenant's VIP threshold)
    is_vip = models.BooleanField(
        default=False,
        help_text='VIP customer status - automatically set when total_spent exceeds tenant VIP threshold'
    )
    
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
            models.Index(fields=['tenant', 'is_vip']),
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
        """Record a purchase and auto-update VIP status"""
        self.total_purchases += amount
        self.total_spent += amount  # Also update total_spent
        self.purchase_count += 1
        self.last_purchase_at = timezone.now()
        self.save(update_fields=['total_purchases', 'total_spent', 'purchase_count', 'last_purchase_at', 'updated_at'])
        
        # Auto-update VIP status after purchase
        self.update_vip_status()
    
    def update_vip_status(self):
        """
        Auto-update VIP status based on tenant's VIP threshold setting.
        Returns True if status changed, False otherwise.
        """
        try:
            # Get tenant's VIP threshold from settings
            tenant_settings = self.tenant.settings
            vip_threshold = tenant_settings.vip_threshold
            
            # Determine new VIP status
            should_be_vip = self.total_spent >= vip_threshold
            
            # Update if changed
            if self.is_vip != should_be_vip:
                self.is_vip = should_be_vip
                self.save(update_fields=['is_vip', 'updated_at'])
                return True
            
            return False
        except Exception as e:
            # If tenant settings don't exist, use default threshold of 1000
            should_be_vip = self.total_spent >= 1000
            if self.is_vip != should_be_vip:
                self.is_vip = should_be_vip
                self.save(update_fields=['is_vip', 'updated_at'])
                return True
            return False


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
    related_name='transactions',
    null=True,
    blank=True,
    help_text='Customer who made the transaction. Null for anonymous/walk-in customers.'
)
    tenant_customer = models.ForeignKey(
        TenantCustomer,
        on_delete=models.CASCADE,
        related_name='transactions',
        null=True,
        blank=True,
        help_text='Tenant-Customer relationship. Null for anonymous transactions.'
    )

    # ADD THIS NEW FIELD right after tenant_customer
    is_anonymous = models.BooleanField(
        default=False,
        help_text='True if this is an anonymous/walk-in customer transaction'
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
    discount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Discount amount"
    )  # 🔗 INTEGRATION: Added for POS sync
    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Total amount (amount + tax - discount)"
    )
    currency = models.CharField(
        max_length=3,
        default='USD',
        help_text="Currency code (ISO 4217)"
    )  # 🔗 INTEGRATION: Added for POS sync
    
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
    transaction_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Human-readable transaction number from POS"
    )  # 🔗 INTEGRATION: Added for POS sync
    receipt_number = models.CharField(max_length=50, blank=True)
    items_description = models.TextField(
        blank=True,
        help_text="Brief description of items purchased"
    )
    items = models.JSONField(
        default=list,
        blank=True,
        help_text="Detailed items list from POS"
    )  # 🔗 INTEGRATION: Added for POS sync
    notes = models.TextField(blank=True, null=True)
    
    # ============================================
    # 🔗 INTEGRATION: POS sync fields
    # ============================================
    external_id = models.UUIDField(
        unique=True,
        null=True,
        blank=True,
        help_text='Transaction ID from POS system',
        db_index=True
    )
    
    external_source = models.CharField(
        max_length=20,
        default='CRM',
        choices=[
            ('CRM', 'CRM'),
            ('POS', 'POS'),
        ],
        help_text='Source system of this transaction'
    )
    
    synced_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When this transaction was synced from POS'
    )
    
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
    created_by = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="ID of user who created transaction in POS"
    )  # 🔗 INTEGRATION: Added for POS sync audit trail
    
    class Meta:
        db_table = 'transactions'
        ordering = ['-transaction_date']
        indexes = [
            models.Index(fields=['tenant', 'customer', '-transaction_date']),
            models.Index(fields=['tenant', '-transaction_date']),
            models.Index(fields=['transaction_id']),
            models.Index(fields=['status']),
            models.Index(fields=['external_id']),  # 🔗 INTEGRATION INDEX
            models.Index(fields=['external_source']),  # 🔗 INTEGRATION INDEX
        ]
        verbose_name = 'Transaction'
        verbose_name_plural = 'Transactions'
    
    @property
    def is_customer_transaction(self):
        """Check if this transaction has a linked customer"""
        return self.customer is not None and not self.is_anonymous

    @property
    def customer_name(self):
        """Get customer name or 'Anonymous Customer' for display"""
        if self.customer:
            return f"{self.customer.first_name} {self.customer.last_name}"
        return "Anonymous Customer"

    def __str__(self):
        """String representation with anonymous support"""
        customer_info = self.customer_name if self.customer else "Anonymous"
        return f"Transaction {self.transaction_number} - {customer_info} - ${self.total}"

    def __str__(self):
        return f"Transaction {self.transaction_id or self.id} - {self.customer.email} - ${self.total}"
    
    def save(self, *args, **kwargs):
        # Auto-generate transaction ID if not provided
        if not self.transaction_id:
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
        # Skip if anonymous transaction or no customer
        if self.is_anonymous or not self.tenant_customer:
            return
        
        if self.transaction_type == 'purchase':
            # Update loyalty points
            self.tenant_customer.loyalty_points += self.points_earned
            self.tenant_customer.loyalty_points -= self.points_redeemed
            # Update total spent
            if not hasattr(self.tenant_customer, 'total_spent'):
                # If field doesn't exist yet, track in total_purchases
                self.tenant_customer.total_purchases += self.total
    
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


# ============================================
# 🔗 INTEGRATION: Sync Log Model
# ============================================

class SyncLog(models.Model):
    """
    Track synchronization operations between POS and CRM
    """
    
    DIRECTION_CHOICES = [
        ('pos_to_crm', 'POS to CRM'),
        ('crm_to_pos', 'CRM to POS'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('retry', 'Retry Scheduled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Operation details
    operation = models.CharField(max_length=50, help_text="Operation type (e.g., 'transaction_sync')")
    direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES, default='pos_to_crm')
    entity_type = models.CharField(max_length=50, help_text="Entity type (e.g., 'transaction', 'customer')")
    entity_id = models.CharField(max_length=100, help_text="ID of the synced entity")
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    attempt_count = models.IntegerField(default=1)
    error_message = models.TextField(blank=True)
    
    # Data
    payload = models.JSONField(help_text="Data that was synced")
    response = models.JSONField(null=True, blank=True, help_text="Response from the target system")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'sync_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['entity_type', 'entity_id']),
            models.Index(fields=['direction']),
            models.Index(fields=['-created_at']),
        ]
        verbose_name = 'Sync Log'
        verbose_name_plural = 'Sync Logs'
    
    def __str__(self):
        return f"{self.operation} - {self.entity_type} {self.entity_id} - {self.status}"


# ============================================
# 🔗 INTEGRATION: System Mapping Model
# ============================================

class SystemMapping(models.Model):
    """
    Maps IDs between POS and CRM systems
    Enables bidirectional ID lookups for customers, businesses, and transactions
    """
    
    ENTITY_TYPE_CHOICES = [
        ('BUSINESS', 'Business'),
        ('CUSTOMER', 'Customer'),
        ('TRANSACTION', 'Transaction'),
    ]
    
    SYNC_STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('PENDING', 'Pending'),
        ('FAILED', 'Failed'),
        ('ARCHIVED', 'Archived'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Mapping details
    entity_type = models.CharField(
        max_length=20,
        choices=ENTITY_TYPE_CHOICES,
        help_text="Type of entity being mapped"
    )
    crm_id = models.CharField(
        max_length=255,
        help_text="UUID in CRM system"
    )
    pos_id = models.CharField(
        max_length=255,
        help_text="ID in POS system"
    )
    
    # Relationships
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='system_mappings',
        help_text="Tenant this mapping belongs to"
    )
    
    # Sync tracking
    last_synced_at = models.DateTimeField(auto_now=True)
    sync_status = models.CharField(
        max_length=20,
        choices=SYNC_STATUS_CHOICES,
        default='ACTIVE'
    )
    
    # Additional data
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata about the mapping"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'system_mappings'
        ordering = ['-created_at']
        unique_together = [
            ('entity_type', 'crm_id'),
            ('entity_type', 'pos_id'),
        ]
        indexes = [
            models.Index(fields=['entity_type', 'crm_id']),
            models.Index(fields=['entity_type', 'pos_id']),
            models.Index(fields=['tenant']),
            models.Index(fields=['entity_type', 'sync_status']),
        ]
        verbose_name = 'System Mapping'
        verbose_name_plural = 'System Mappings'
    
    def __str__(self):
        return f"{self.entity_type}: {self.crm_id} <-> {self.pos_id}"