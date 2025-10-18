"""
Rewards Models for Ayende CRMForce
Comprehensive loyalty rewards and redemption system
"""

from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
import uuid


class Reward(models.Model):
    """
    Rewards that customers can redeem with loyalty points.
    Supports both discount vouchers and actual products/services.
    """
    
    REWARD_TYPE_CHOICES = [
        ('discount', 'Discount Voucher'),
        ('product', 'Product/Service'),
        ('gift', 'Free Gift'),
        ('upgrade', 'Service Upgrade'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('expired', 'Expired'),
        ('out_of_stock', 'Out of Stock'),
    ]
    
    # Identification
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Tenant relationship
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='rewards'
    )
    
    # Basic Information
    name = models.CharField(
        max_length=200,
        help_text="Reward name (e.g., '$5 Off', 'Free Coffee')"
    )
    description = models.TextField(
        help_text="Detailed description of the reward"
    )
    reward_type = models.CharField(
        max_length=20,
        choices=REWARD_TYPE_CHOICES,
        default='discount'
    )
    
    # Visual
    image = models.ImageField(
        upload_to='rewards/',
        blank=True,
        null=True,
        help_text="Reward image/thumbnail"
    )
    
    # Point Requirements
    points_required = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Points needed to redeem this reward"
    )
    
    # Discount Information (for discount type rewards)
    discount_type = models.CharField(
        max_length=20,
        choices=[
            ('percentage', 'Percentage Off'),
            ('fixed', 'Fixed Amount Off'),
        ],
        blank=True,
        help_text="Type of discount (only for discount rewards)"
    )
    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Discount amount (e.g., 10 for 10% or $10)"
    )
    minimum_purchase = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Minimum purchase amount required to use this reward"
    )
    
    # Stock Management
    has_stock_limit = models.BooleanField(
        default=False,
        help_text="Enable stock limit for this reward"
    )
    total_stock = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Total available stock"
    )
    redeemed_count = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Number of times redeemed"
    )
    
    # Expiration
    has_expiration = models.BooleanField(
        default=False,
        help_text="Enable expiration date"
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Reward expiration date"
    )
    
    # Redemption Limits
    limit_per_customer = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Maximum redemptions per customer (0 = unlimited)"
    )
    
    # Validity Period (after redemption)
    validity_days = models.IntegerField(
        default=30,
        validators=[MinValueValidator(0)],
        help_text="Days until redeemed reward expires (0 = no expiration)"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active'
    )
    is_featured = models.BooleanField(
        default=False,
        help_text="Show as featured reward"
    )
    
    # Terms & Conditions
    terms_conditions = models.TextField(
        blank=True,
        help_text="Terms and conditions for this reward"
    )
    
    # Ordering
    display_order = models.IntegerField(
        default=0,
        help_text="Display order in catalog (lower = first)"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'customers.Customer',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_rewards'
    )
    
    class Meta:
        db_table = 'rewards'
        ordering = ['display_order', '-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'is_featured']),
            models.Index(fields=['points_required']),
        ]
        verbose_name = 'Reward'
        verbose_name_plural = 'Rewards'
    
    def __str__(self):
        return f"{self.name} ({self.points_required} points)"
    
    @property
    def is_available(self):
        """Check if reward is currently available for redemption"""
        # Check status
        if self.status != 'active':
            return False
        
        # Check expiration
        if self.has_expiration and self.expires_at:
            if timezone.now() > self.expires_at:
                return False
        
        # Check stock
        if self.has_stock_limit:
            remaining = self.total_stock - self.redeemed_count
            if remaining <= 0:
                return False
        
        return True
    
    @property
    def stock_remaining(self):
        """Calculate remaining stock"""
        if not self.has_stock_limit:
            return None
        return max(0, self.total_stock - self.redeemed_count)
    
    @property
    def is_low_stock(self):
        """Check if stock is running low (less than 10%)"""
        if not self.has_stock_limit:
            return False
        remaining = self.stock_remaining
        if remaining is None:
            return False
        return remaining <= (self.total_stock * 0.1)
    
    def can_be_redeemed_by(self, tenant_customer):
        """Check if specific customer can redeem this reward"""
        # Check availability
        if not self.is_available:
            return False, "This reward is currently unavailable"
        
        # Check points
        if tenant_customer.loyalty_points < self.points_required:
            return False, f"You need {self.points_required - tenant_customer.loyalty_points} more points"
        
        # Check customer redemption limit
        if self.limit_per_customer > 0:
            customer_redemptions = Redemption.objects.filter(
                reward=self,
                tenant_customer=tenant_customer,
                status__in=['pending', 'approved', 'used']
            ).count()
            
            if customer_redemptions >= self.limit_per_customer:
                return False, f"You have reached the redemption limit for this reward"
        
        return True, "Can redeem"
    
    def increment_redemption_count(self):
        """Increment the redemption counter"""
        self.redeemed_count += 1
        
        # Auto-update status if out of stock
        if self.has_stock_limit and self.stock_remaining <= 0:
            self.status = 'out_of_stock'
        
        self.save(update_fields=['redeemed_count', 'status', 'updated_at'])


class Redemption(models.Model):
    """
    Track customer reward redemptions.
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('used', 'Used'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
        ('rejected', 'Rejected'),
    ]
    
    # Identification
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    redemption_code = models.CharField(
        max_length=20,
        unique=True,
        help_text="Unique redemption code"
    )
    
    # Relationships
    reward = models.ForeignKey(
        Reward,
        on_delete=models.PROTECT,
        related_name='redemptions'
    )
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='redemptions'
    )
    tenant_customer = models.ForeignKey(
        'customers.TenantCustomer',
        on_delete=models.CASCADE,
        related_name='redemptions'
    )
    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.CASCADE,
        related_name='redemptions'
    )
    
    # Redemption Details
    points_spent = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text="Points spent on this redemption"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    # Validity
    valid_from = models.DateTimeField(
        default=timezone.now,
        help_text="When this redemption becomes valid"
    )
    valid_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this redemption expires"
    )
    
    # Usage Tracking
    used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the reward was used/claimed"
    )
    used_by_staff = models.ForeignKey(
        'customers.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_redemptions',
        help_text="Staff member who processed the redemption"
    )
    
    # Transaction Link (if used in a purchase)
    transaction = models.ForeignKey(
        'customers.Transaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='redemptions_used',
        help_text="Transaction where this was used"
    )
    
    # Notes
    customer_note = models.TextField(
        blank=True,
        help_text="Customer's note/message"
    )
    staff_note = models.TextField(
        blank=True,
        help_text="Internal staff notes"
    )
    rejection_reason = models.TextField(
        blank=True,
        help_text="Reason for rejection (if applicable)"
    )
    
    # Timestamps
    redeemed_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'redemptions'
        ordering = ['-redeemed_at']
        indexes = [
            models.Index(fields=['tenant', 'customer', '-redeemed_at']),
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['redemption_code']),
            models.Index(fields=['status', 'valid_until']),
        ]
        verbose_name = 'Redemption'
        verbose_name_plural = 'Redemptions'
    
    def __str__(self):
        return f"{self.redemption_code} - {self.reward.name}"
    
    def save(self, *args, **kwargs):
        # Generate unique redemption code if not exists
        if not self.redemption_code:
            self.redemption_code = self.generate_redemption_code()
        
        # Set validity period
        if not self.valid_until and self.reward.validity_days > 0:
            from datetime import timedelta
            self.valid_until = self.valid_from + timedelta(days=self.reward.validity_days)
        
        super().save(*args, **kwargs)
    
    def generate_redemption_code(self):
        """Generate unique redemption code"""
        import random
        import string
        
        while True:
            # Format: RWD-XXXXXX (6 random uppercase letters/numbers)
            code = 'RWD-' + ''.join(
                random.choices(string.ascii_uppercase + string.digits, k=6)
            )
            
            # Check if code exists
            if not Redemption.objects.filter(redemption_code=code).exists():
                return code
    
    @property
    def is_valid(self):
        """Check if redemption is currently valid"""
        if self.status not in ['pending', 'approved']:
            return False
        
        now = timezone.now()
        
        # Check if started
        if now < self.valid_from:
            return False
        
        # Check if expired
        if self.valid_until and now > self.valid_until:
            return False
        
        return True
    
    @property
    def is_expired(self):
        """Check if redemption has expired"""
        if not self.valid_until:
            return False
        return timezone.now() > self.valid_until
    
    @property
    def days_until_expiry(self):
        """Calculate days until expiration"""
        if not self.valid_until:
            return None
        
        delta = self.valid_until - timezone.now()
        return max(0, delta.days)
    
    def approve(self, staff_member=None):
        """Approve the redemption"""
        self.status = 'approved'
        if staff_member:
            self.used_by_staff = staff_member
        self.save(update_fields=['status', 'used_by_staff', 'updated_at'])
    
    def use(self, staff_member=None, transaction=None):
        """Mark redemption as used"""
        self.status = 'used'
        self.used_at = timezone.now()
        if staff_member:
            self.used_by_staff = staff_member
        if transaction:
            self.transaction = transaction
        self.save(update_fields=['status', 'used_at', 'used_by_staff', 'transaction', 'updated_at'])
    
    def cancel(self, refund_points=True):
        """Cancel redemption and optionally refund points"""
        self.status = 'cancelled'
        
        if refund_points:
            # Refund points to customer
            self.tenant_customer.loyalty_points += self.points_spent
            self.tenant_customer.save(update_fields=['loyalty_points', 'updated_at'])
            
            # Decrement reward redemption count
            self.reward.redeemed_count = max(0, self.reward.redeemed_count - 1)
            self.reward.save(update_fields=['redeemed_count', 'updated_at'])
        
        self.save(update_fields=['status', 'updated_at'])
    
    def reject(self, reason, refund_points=True):
        """Reject redemption request"""
        self.status = 'rejected'
        self.rejection_reason = reason
        
        if refund_points:
            # Refund points
            self.tenant_customer.loyalty_points += self.points_spent
            self.tenant_customer.save(update_fields=['loyalty_points', 'updated_at'])
            
            # Decrement reward redemption count
            self.reward.redeemed_count = max(0, self.reward.redeemed_count - 1)
            self.reward.save(update_fields=['redeemed_count', 'updated_at'])
        
        self.save(update_fields=['status', 'rejection_reason', 'updated_at'])


class RewardCategory(models.Model):
    """
    Optional: Organize rewards into categories.
    """
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='reward_categories'
    )
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="Icon class or emoji"
    )
    display_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    # Link rewards to categories
    rewards = models.ManyToManyField(
        Reward,
        related_name='categories',
        blank=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'reward_categories'
        ordering = ['display_order', 'name']
        verbose_name = 'Reward Category'
        verbose_name_plural = 'Reward Categories'
        unique_together = ['tenant', 'name']
    
    def __str__(self):
        return self.name
