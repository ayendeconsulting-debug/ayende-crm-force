"""
FIX: Tenant Admin - Complete with subdomain and subscription_status
Resolves: 
1. Missing subdomain field preventing tenant creation via admin
2. Missing subscription_status field
3. Auto-set owner_id to prevent NOT NULL constraint
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.text import slugify
from unfold.admin import ModelAdmin
from unfold.decorators import display
from .models import Tenant, TenantSettings


@admin.register(Tenant)
class TenantAdmin(ModelAdmin):
    """
    Modern admin interface for Tenant model
    FIXED: Includes subdomain and subscription_status fields
    """
    
    list_display = [
        'tenant_uuid',
        'display_name_with_status',
        'subdomain',
        'display_subscription_status',
        'display_currency',
        'created_at'
    ]
    
    list_filter = [
        'is_active',
        'subscription_status',
        'currency',
        'created_at',
    ]
    
    search_fields = [
        'name',
        'slug',
        'subdomain',
        'tenant_uuid',
    ]
    
    readonly_fields = [
        'id',
        'tenant_uuid',
        'created_at',
        'updated_at',
    ]
    
    fieldsets = [
        ('Basic Information', {
            'fields': (
                'tenant_uuid',
                'name',
                'subdomain',
                'slug',
                'description',
            ),
            'classes': ('wide',),
            'description': 'Tenant UUID is auto-generated. Subdomain will be used for tenant URL (e.g., simistore.ayendecx.com). Slug will auto-populate from subdomain if left empty.',
        }),
        ('Regional Settings', {
            'fields': (
                'currency',
                'currency_symbol',
                'currency_position',
                'decimal_places',
            ),
            'classes': ('wide',),
            'description': 'Select currency and the symbol will auto-populate. Customize if needed.',
        }),
        ('Branding', {
            'fields': (
                'logo',
                'primary_color',
                'secondary_color',
            ),
            'classes': ('collapse',),
        }),
        ('Subscription & Status', {
            'fields': (
                'subscription_status',
                'is_active',
            ),
            'classes': ('wide',),
            'description': 'Manage subscription status and tenant activation.',
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',),
        }),
    ]
    
    # Prepopulate slug from subdomain
    prepopulated_fields = {
        'slug': ('subdomain',),
    }
    
    # Add custom CSS and JavaScript
    class Media:
        css = {
            'all': ('admin/css/tenant_admin.css',)
        }
        js = ('admin/js/tenant_admin.js',)
    
    @display(description='Business Name')
    def display_name_with_status(self, obj):
        """Display tenant name with active status badge - Unfold compatible"""
        if obj.is_active:
            badge_html = '<span class="badge badge-success">ACTIVE</span>'
        else:
            badge_html = '<span class="badge badge-danger">INACTIVE</span>'
        
        return mark_safe(f'<strong>{obj.name}</strong> {badge_html}')
    
    @display(description='Subscription')
    def display_subscription_status(self, obj):
        """Display subscription status with color-coded badge"""
        status_colors = {
            'trial': 'info',      # Blue
            'active': 'success',  # Green
            'inactive': 'secondary',  # Gray
            'suspended': 'warning',   # Yellow/Orange
            'cancelled': 'danger',    # Red
        }
        
        color = status_colors.get(obj.subscription_status, 'secondary')
        status_display = obj.get_subscription_status_display()
        
        return mark_safe(f'<span class="badge badge-{color}">{status_display.upper()}</span>')
    
    @display(description='Currency')
    def display_currency(self, obj):
        """Display currency with symbol - Unfold compatible"""
        symbol = getattr(obj, 'currency_symbol', '$')
        currency = getattr(obj, 'currency', 'USD')
        return mark_safe(f'<code>{symbol} {currency}</code>')
    
    def save_model(self, request, obj, form, change):
        """
        Auto-populate fields when saving:
        1. Currency symbol based on currency selection
        2. Owner to current user (for new tenants)
        3. Slug from subdomain if slug is empty
        """
        # Currency symbol mapping
        currency_symbols = {
            'USD': '$',
            'CAD': 'C$',
            'GBP': '£',
            'EUR': '€',
            'AUD': 'A$',
            'NGN': '₦',
            'ZAR': 'R',
            'KES': 'KSh',
            'GHS': 'GH₵',
            'UGX': 'USh',
            'TZS': 'TSh',
            'EGP': 'E£',
            'MAD': 'DH',
            'JPY': '¥',
            'CNY': '¥',
            'INR': '₹',
            'CHF': 'CHF',
        }
        
        # Auto-populate currency symbol
        currency = getattr(obj, 'currency', None)
        current_symbol = getattr(obj, 'currency_symbol', '$')
        
        if currency and (not current_symbol or current_symbol == '$'):
            obj.currency_symbol = currency_symbols.get(currency, '$')
        
        # Auto-populate slug from subdomain if slug is empty
        if not obj.slug and obj.subdomain:
            obj.slug = slugify(obj.subdomain)
        
        # Auto-set owner to current user if not set (for new tenants)
        if not change and not obj.owner_id:
            obj.owner = request.user
        
        super().save_model(request, obj, form, change)


@admin.register(TenantSettings)
class TenantSettingsAdmin(ModelAdmin):
    """
    Admin interface for Tenant Settings
    """
    list_display = [
        'tenant',
        'allow_customer_registration',
        'enable_loyalty_points',
        'max_customers',
    ]
    
    list_filter = [
        'allow_customer_registration',
        'enable_loyalty_points',
        'enable_email_notifications',
    ]
    
    search_fields = [
        'tenant__name',
    ]
    
    fieldsets = [
        ('Registration Settings', {
            'fields': (
                'tenant',
                'allow_customer_registration',
                'require_email_verification',
            ),
        }),
        ('Limits', {
            'fields': (
                'max_customers',
                'max_staff_members',
            ),
        }),
        ('Loyalty Program', {
            'fields': (
                'enable_loyalty_points',
                'points_per_dollar',
            ),
        }),
        ('Notifications', {
            'fields': (
                'enable_email_notifications',
                'enable_sms_notifications',
            ),
        }),
        ('Business Information', {
            'fields': (
                'business_hours',
            ),
            'classes': ('collapse',),
        }),
    ]