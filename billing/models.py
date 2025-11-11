"""
Billing Models for Ayende CX Platform
Handles subscriptions, invoices, payments, and professional fees
"""

from django.db import models
from django.utils import timezone
from decimal import Decimal
import uuid


class SubscriptionPlan(models.Model):
    """
    Subscription plans offered by the platform
    """
    BILLING_CYCLE_CHOICES = [
        ('monthly', 'Monthly'),
        ('annual', 'Annual'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, help_text="Plan name (e.g., Starter, Professional)")
    description = models.TextField(blank=True)
    billing_cycle = models.CharField(max_length=20, choices=BILLING_CYCLE_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price in USD")
    
    # Features
    max_customers = models.IntegerField(default=100, help_text="Maximum customers allowed")
    max_transactions_per_month = models.IntegerField(default=1000, help_text="Max transactions per month")
    max_staff_users = models.IntegerField(default=5, help_text="Maximum staff users")
    
    # Features flags
    has_analytics = models.BooleanField(default=True)
    has_api_access = models.BooleanField(default=False)
    has_custom_branding = models.BooleanField(default=False)
    has_priority_support = models.BooleanField(default=False)
    
    # Trial
    trial_days = models.IntegerField(default=14, help_text="Trial period in days")
    
    # Status
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['price']
        verbose_name = 'Subscription Plan'
        verbose_name_plural = 'Subscription Plans'
    
    def __str__(self):
        return f"{self.name} - ${self.price}/{self.billing_cycle}"
    
    @property
    def monthly_price(self):
        """Convert to monthly equivalent for comparison"""
        if self.billing_cycle == 'annual':
            return self.price / 12
        return self.price


class TenantSubscription(models.Model):
    """
    Tracks tenant subscriptions to platform plans
    """
    STATUS_CHOICES = [
        ('trial', 'Trial'),
        ('active', 'Active'),
        ('past_due', 'Past Due'),
        ('canceled', 'Canceled'),
        ('expired', 'Expired'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.OneToOneField('tenants.Tenant', on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='trial')
    
    # Dates
    trial_start_date = models.DateField(null=True, blank=True)
    trial_end_date = models.DateField(null=True, blank=True)
    start_date = models.DateField(help_text="Subscription start date")
    end_date = models.DateField(null=True, blank=True, help_text="For annual plans")
    next_billing_date = models.DateField()
    canceled_at = models.DateTimeField(null=True, blank=True)
    
    # Auto-renewal
    auto_renew = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Tenant Subscription'
        verbose_name_plural = 'Tenant Subscriptions'
    
    def __str__(self):
        return f"{self.tenant.name} - {self.plan.name} ({self.status})"
    
    @property
    def is_trial(self):
        return self.status == 'trial'
    
    @property
    def is_active(self):
        return self.status in ['trial', 'active']
    
    @property
    def days_until_renewal(self):
        if self.next_billing_date:
            delta = self.next_billing_date - timezone.now().date()
            return delta.days
        return None
    
    def calculate_mrr(self):
        """Monthly Recurring Revenue for this subscription"""
        if self.plan.billing_cycle == 'monthly':
            return self.plan.price
        elif self.plan.billing_cycle == 'annual':
            return self.plan.price / 12
        return Decimal('0')


class ProfessionalFeeType(models.Model):
    """
    Types of professional fees that can be charged
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, help_text="Fee type (e.g., Setup, Training)")
    description = models.TextField(blank=True)
    default_amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Default price")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Professional Fee Type'
        verbose_name_plural = 'Professional Fee Types'
    
    def __str__(self):
        return f"{self.name} - ${self.default_amount}"


class ProfessionalFee(models.Model):
    """
    Professional services fees charged to tenants
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('invoiced', 'Invoiced'),
        ('paid', 'Paid'),
        ('canceled', 'Canceled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='professional_fees')
    fee_type = models.ForeignKey(ProfessionalFeeType, on_delete=models.PROTECT)
    
    description = models.TextField(help_text="Detailed description of service")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Dates
    service_date = models.DateField(default=timezone.now)
    due_date = models.DateField(null=True, blank=True)
    paid_date = models.DateField(null=True, blank=True)
    
    # Link to invoice
    invoice = models.ForeignKey('PlatformInvoice', on_delete=models.SET_NULL, null=True, blank=True, related_name='fees')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Professional Fee'
        verbose_name_plural = 'Professional Fees'
    
    def __str__(self):
        return f"{self.tenant.name} - {self.fee_type.name} - ${self.amount}"


class PlatformInvoice(models.Model):
    """
    Invoices sent to tenants for platform services
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('canceled', 'Canceled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice_number = models.CharField(max_length=50, unique=True, help_text="INV-2025-0001")
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='invoices')
    
    # Amounts
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Dates
    issue_date = models.DateField(default=timezone.now)
    due_date = models.DateField()
    paid_date = models.DateField(null=True, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Platform Invoice'
        verbose_name_plural = 'Platform Invoices'
    
    def __str__(self):
        return f"{self.invoice_number} - {self.tenant.name} - ${self.total_amount}"
    
    @property
    def is_overdue(self):
        if self.status == 'sent' and self.due_date < timezone.now().date():
            return True
        return False
    
    def calculate_total(self):
        """Calculate total from line items"""
        # Subscription charges
        subscription_total = Decimal('0')
        
        # Professional fees
        fees_total = self.fees.aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0')
        
        self.subtotal = subscription_total + fees_total
        self.total_amount = self.subtotal + self.tax_amount
        return self.total_amount


class InvoiceLineItem(models.Model):
    """
    Line items in an invoice (for subscription charges)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(PlatformInvoice, on_delete=models.CASCADE, related_name='line_items')
    
    description = models.CharField(max_length=255)
    quantity = models.IntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Link to subscription if applicable
    subscription = models.ForeignKey(TenantSubscription, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['id']
        verbose_name = 'Invoice Line Item'
        verbose_name_plural = 'Invoice Line Items'
    
    def __str__(self):
        return f"{self.description} - ${self.total}"
    
    def save(self, *args, **kwargs):
        self.total = self.quantity * self.unit_price
        super().save(*args, **kwargs)


class PlatformPayment(models.Model):
    """
    Payments received from tenants
    """
    PAYMENT_METHOD_CHOICES = [
        ('credit_card', 'Credit Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('check', 'Check'),
        ('paypal', 'PayPal'),
        ('stripe', 'Stripe'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='payments')
    invoice = models.ForeignKey(PlatformInvoice, on_delete=models.CASCADE, related_name='payments')
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Payment details
    transaction_id = models.CharField(max_length=255, blank=True, help_text="External payment ID")
    payment_date = models.DateTimeField(default=timezone.now)
    
    # Notes
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-payment_date']
        verbose_name = 'Platform Payment'
        verbose_name_plural = 'Platform Payments'
    
    def __str__(self):
        return f"{self.tenant.name} - ${self.amount} - {self.status}"


class RevenueMetrics(models.Model):
    """
    Cached revenue metrics for dashboard performance
    Updated daily via management command
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date = models.DateField(unique=True)
    
    # Revenue metrics
    daily_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    mrr = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Monthly Recurring Revenue")
    arr = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Annual Recurring Revenue")
    
    # Subscription metrics
    active_subscriptions = models.IntegerField(default=0)
    trial_subscriptions = models.IntegerField(default=0)
    canceled_subscriptions = models.IntegerField(default=0)
    
    # Payment metrics
    outstanding_invoices = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overdue_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date']
        verbose_name = 'Revenue Metrics'
        verbose_name_plural = 'Revenue Metrics'
    
    def __str__(self):
        return f"{self.date} - MRR: ${self.mrr} - ARR: ${self.arr}"