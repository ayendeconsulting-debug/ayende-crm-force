"""
Admin Interface for Billing System
Allows platform admins to manage subscriptions, invoices, payments, and fees
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Sum
from decimal import Decimal
from .models import (
    SubscriptionPlan,
    TenantSubscription,
    ProfessionalFeeType,
    ProfessionalFee,
    PlatformInvoice,
    InvoiceLineItem,
    PlatformPayment,
    RevenueMetrics
)


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'billing_cycle', 'price_display', 'trial_days', 'max_customers', 'is_active']
    list_filter = ['billing_cycle', 'is_active']
    search_fields = ['name', 'description']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'billing_cycle', 'price', 'is_active')
        }),
        ('Limits', {
            'fields': ('max_customers', 'max_transactions_per_month', 'max_staff_users')
        }),
        ('Features', {
            'fields': ('has_analytics', 'has_api_access', 'has_custom_branding', 'has_priority_support')
        }),
        ('Trial', {
            'fields': ('trial_days',)
        }),
    )
    
    def price_display(self, obj):
        return f"${obj.price}/{obj.billing_cycle}"
    price_display.short_description = 'Price'


@admin.register(TenantSubscription)
class TenantSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'plan', 'status_badge', 'start_date', 'next_billing_date', 'days_remaining', 'auto_renew']
    list_filter = ['status', 'plan', 'auto_renew']
    search_fields = ['tenant__name', 'tenant__subdomain']
    readonly_fields = ['created_at', 'updated_at', 'mrr_display']
    
    fieldsets = (
        ('Subscription Details', {
            'fields': ('tenant', 'plan', 'status', 'auto_renew')
        }),
        ('Trial Period', {
            'fields': ('trial_start_date', 'trial_end_date')
        }),
        ('Billing Dates', {
            'fields': ('start_date', 'end_date', 'next_billing_date')
        }),
        ('Revenue', {
            'fields': ('mrr_display',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'canceled_at'),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'trial': '#fbbf24',
            'active': '#10b981',
            'past_due': '#ef4444',
            'canceled': '#6b7280',
            'expired': '#6b7280',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 12px; border-radius: 12px; font-weight: 600; font-size: 0.75rem;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def days_remaining(self, obj):
        days = obj.days_until_renewal
        if days is not None:
            if days < 0:
                return format_html('<span style="color: red;">Overdue by {} days</span>', abs(days))
            elif days <= 7:
                return format_html('<span style="color: orange;">{} days</span>', days)
            return f"{days} days"
        return "-"
    days_remaining.short_description = 'Days to Renewal'
    
    def mrr_display(self, obj):
        mrr = obj.calculate_mrr()
        return f"${mrr:.2f}/month"
    mrr_display.short_description = 'MRR Contribution'


@admin.register(ProfessionalFeeType)
class ProfessionalFeeTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'default_amount_display', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    
    def default_amount_display(self, obj):
        return f"${obj.default_amount}"
    default_amount_display.short_description = 'Default Amount'


@admin.register(ProfessionalFee)
class ProfessionalFeeAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'fee_type', 'amount_display', 'status_badge', 'service_date', 'paid_date']
    list_filter = ['status', 'fee_type', 'service_date']
    search_fields = ['tenant__name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Fee Details', {
            'fields': ('tenant', 'fee_type', 'description', 'amount', 'status')
        }),
        ('Dates', {
            'fields': ('service_date', 'due_date', 'paid_date')
        }),
        ('Invoice', {
            'fields': ('invoice',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def amount_display(self, obj):
        return f"${obj.amount}"
    amount_display.short_description = 'Amount'
    
    def status_badge(self, obj):
        colors = {
            'pending': '#6b7280',
            'invoiced': '#3b82f6',
            'paid': '#10b981',
            'canceled': '#ef4444',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 12px; border-radius: 12px; font-weight: 600; font-size: 0.75rem;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'


class InvoiceLineItemInline(admin.TabularInline):
    model = InvoiceLineItem
    extra = 1
    fields = ['description', 'quantity', 'unit_price', 'total']
    readonly_fields = ['total']


class ProfessionalFeeInline(admin.TabularInline):
    model = ProfessionalFee
    extra = 0
    fields = ['fee_type', 'description', 'amount', 'status']
    readonly_fields = ['fee_type', 'description', 'amount']
    can_delete = False


@admin.register(PlatformInvoice)
class PlatformInvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'tenant', 'total_display', 'status_badge', 'issue_date', 'due_date', 'is_overdue_display']
    list_filter = ['status', 'issue_date', 'due_date']
    search_fields = ['invoice_number', 'tenant__name']
    readonly_fields = ['created_at', 'updated_at', 'subtotal_display', 'total_display_readonly']
    inlines = [InvoiceLineItemInline, ProfessionalFeeInline]
    
    fieldsets = (
        ('Invoice Details', {
            'fields': ('invoice_number', 'tenant', 'status')
        }),
        ('Amounts', {
            'fields': ('subtotal', 'tax_amount', 'total_amount', 'subtotal_display', 'total_display_readonly')
        }),
        ('Dates', {
            'fields': ('issue_date', 'due_date', 'paid_date')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_paid', 'mark_as_sent', 'mark_as_overdue']
    
    def total_display(self, obj):
        return f"${obj.total_amount}"
    total_display.short_description = 'Total'
    
    def subtotal_display(self, obj):
        return f"${obj.subtotal}"
    subtotal_display.short_description = 'Subtotal'
    
    def total_display_readonly(self, obj):
        return f"${obj.total_amount}"
    total_display_readonly.short_description = 'Total Amount'
    
    def status_badge(self, obj):
        colors = {
            'draft': '#6b7280',
            'sent': '#3b82f6',
            'paid': '#10b981',
            'overdue': '#ef4444',
            'canceled': '#6b7280',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 12px; border-radius: 12px; font-weight: 600; font-size: 0.75rem;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def is_overdue_display(self, obj):
        if obj.is_overdue:
            return format_html('<span style="color: red; font-weight: bold;">⚠️ OVERDUE</span>')
        return "-"
    is_overdue_display.short_description = 'Overdue'
    
    def mark_as_paid(self, request, queryset):
        from django.utils import timezone
        queryset.update(status='paid', paid_date=timezone.now().date())
        self.message_user(request, f"{queryset.count()} invoice(s) marked as paid.")
    mark_as_paid.short_description = "Mark selected invoices as paid"
    
    def mark_as_sent(self, request, queryset):
        queryset.update(status='sent')
        self.message_user(request, f"{queryset.count()} invoice(s) marked as sent.")
    mark_as_sent.short_description = "Mark selected invoices as sent"
    
    def mark_as_overdue(self, request, queryset):
        queryset.update(status='overdue')
        self.message_user(request, f"{queryset.count()} invoice(s) marked as overdue.")
    mark_as_overdue.short_description = "Mark selected invoices as overdue"


@admin.register(PlatformPayment)
class PlatformPaymentAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'invoice_link', 'amount_display', 'payment_method', 'status_badge', 'payment_date']
    list_filter = ['status', 'payment_method', 'payment_date']
    search_fields = ['tenant__name', 'transaction_id', 'invoice__invoice_number']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Payment Details', {
            'fields': ('tenant', 'invoice', 'amount', 'payment_method', 'status')
        }),
        ('Transaction Info', {
            'fields': ('transaction_id', 'payment_date')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def amount_display(self, obj):
        return f"${obj.amount}"
    amount_display.short_description = 'Amount'
    
    def invoice_link(self, obj):
        if obj.invoice:
            url = reverse('admin:billing_platforminvoice_change', args=[obj.invoice.id])
            return format_html('<a href="{}">{}</a>', url, obj.invoice.invoice_number)
        return "-"
    invoice_link.short_description = 'Invoice'
    
    def status_badge(self, obj):
        colors = {
            'pending': '#fbbf24',
            'completed': '#10b981',
            'failed': '#ef4444',
            'refunded': '#6b7280',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 12px; border-radius: 12px; font-weight: 600; font-size: 0.75rem;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'


@admin.register(RevenueMetrics)
class RevenueMetricsAdmin(admin.ModelAdmin):
    list_display = ['date', 'mrr_display', 'arr_display', 'daily_revenue_display', 'active_subscriptions', 'outstanding_display']
    list_filter = ['date']
    readonly_fields = ['date', 'daily_revenue', 'mrr', 'arr', 'active_subscriptions', 'trial_subscriptions', 
                      'canceled_subscriptions', 'outstanding_invoices', 'overdue_amount', 'created_at']
    
    def has_add_permission(self, request):
        return False  # Metrics are auto-generated
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # Only superusers can delete
    
    def mrr_display(self, obj):
        return f"${obj.mrr:,.2f}"
    mrr_display.short_description = 'MRR'
    
    def arr_display(self, obj):
        return f"${obj.arr:,.2f}"
    arr_display.short_description = 'ARR'
    
    def daily_revenue_display(self, obj):
        return f"${obj.daily_revenue:,.2f}"
    daily_revenue_display.short_description = 'Daily Revenue'
    
    def outstanding_display(self, obj):
        return f"${obj.outstanding_invoices:,.2f}"
    outstanding_display.short_description = 'Outstanding'