"""
FIX: Tenant Admin - Complete with trial period management
Features:
1. Subdomain and subscription_status fields
2. Tenant UUID with pattern a-cx-{Random-5}
3. Trial period tracking with days remaining display
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.text import slugify
from django.utils import timezone
from unfold.admin import ModelAdmin
from unfold.decorators import display
from .models import Tenant, TenantSettings


@admin.register(Tenant)
class TenantAdmin(ModelAdmin):
    """
    Modern admin interface for Tenant model with trial period management
    """
    
    list_display = [
        'tenant_uuid',
        'display_name_with_status',
        'subdomain',
        'display_subscription_with_trial',
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
        'display_trial_status',
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
        ('Subscription & Trial Management', {
            'fields': (
                'subscription_status',
                'trial_ends_at',
                'display_trial_status',
                'is_active',
            ),
            'classes': ('wide',),
            'description': 'Manage subscription status and trial period. New trial tenants automatically get 14-day trial period.',
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
        """Display tenant name with active status badge"""
        if obj.is_active:
            badge_html = '<span class="badge badge-success">ACTIVE</span>'
        else:
            badge_html = '<span class="badge badge-danger">INACTIVE</span>'
        
        return mark_safe(f'<strong>{obj.name}</strong> {badge_html}')
    
    @display(description='Subscription')
    def display_subscription_with_trial(self, obj):
        """Display subscription status with trial info if applicable"""
        status_colors = {
            'trial': 'info',
            'active': 'success',
            'inactive': 'secondary',
            'suspended': 'warning',
            'cancelled': 'danger',
        }
        
        color = status_colors.get(obj.subscription_status, 'secondary')
        status_display = obj.get_subscription_status_display()
        
        # Add trial days remaining if on trial
        if obj.subscription_status == 'trial' and obj.trial_ends_at:
            days_remaining = obj.trial_days_remaining
            
            if days_remaining is not None:
                if days_remaining > 0:
                    trial_info = f' ({days_remaining}d left)'
                    color = 'info'
                else:
                    trial_info = ' (EXPIRED)'
                    color = 'danger'
                
                return mark_safe(
                    f'<span class="badge badge-{color}">{status_display.upper()}{trial_info}</span>'
                )
        
        return mark_safe(f'<span class="badge badge-{color}">{status_display.upper()}</span>')
    
    @display(description='Trial Status')
    def display_trial_status(self, obj):
        """Display detailed trial status in the form"""
        if obj.subscription_status != 'trial':
            return mark_safe('<span style="color: #666;">Not on trial</span>')
        
        if not obj.trial_ends_at:
            return mark_safe('<span style="color: #ff9800;">Trial end date not set</span>')
        
        days_remaining = obj.trial_days_remaining
        
        if days_remaining is None:
            return mark_safe('<span style="color: #666;">N/A</span>')
        
        if days_remaining > 7:
            color = '#4caf50'  # Green
            status = f'✓ {days_remaining} days remaining'
        elif days_remaining > 0:
            color = '#ff9800'  # Orange
            status = f'⚠ {days_remaining} days remaining'
        else:
            color = '#f44336'  # Red
            status = '✗ Trial expired'
        
        trial_end_date = obj.trial_ends_at.strftime('%B %d, %Y at %I:%M %p')
        
        return mark_safe(
            f'<div style="color: {color}; font-weight: bold;">{status}</div>'
            f'<div style="color: #666; font-size: 0.9em; margin-top: 4px;">Ends: {trial_end_date}</div>'
        )
    
    @display(description='Currency')
    def display_currency(self, obj):
        """Display currency with symbol"""
        symbol = getattr(obj, 'currency_symbol', '$')
        currency = getattr(obj, 'currency', 'USD')
        return mark_safe(f'<code>{symbol} {currency}</code>')
    
    def save_model(self, request, obj, form, change):
        """
        Auto-populate fields when saving:
        1. Currency symbol based on currency selection
        2. Owner to current user (for new tenants)
        3. Slug from subdomain if slug is empty
        4. Trial end date for new trial tenants
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