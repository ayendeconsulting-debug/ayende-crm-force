"""
FIX: Tenant Admin - Auto-set owner_id
Resolves: NOT NULL constraint failed: tenants.owner_id
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin
from unfold.decorators import display
from .models import Tenant


@admin.register(Tenant)
class TenantAdmin(ModelAdmin):
    """
    Modern admin interface for Tenant model with currency auto-population
    FIXED: Auto-sets owner to current logged-in user
    """
    
    list_display = [
        'display_name_with_status', 
        'slug', 
        'display_currency',
        'created_at'
    ]
    
    list_filter = [
        'currency',
        'is_active',
        'created_at',
    ]
    
    search_fields = [
        'name',
        'slug',
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
    ]
    
    fieldsets = [
        ('Basic Information', {
            'fields': (
                'name',
                'slug',
                'description',
            ),
            'classes': ('wide',),
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
        ('Status', {
            'fields': (
                'is_active',
            ),
            'classes': ('wide',),
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',),
        }),
    ]
    
    # Add custom CSS and JavaScript
    class Media:
        css = {
            'all': ('admin/css/tenant_admin.css',)
        }
        js = ('admin/js/tenant_admin.js',)
    
    @display(description='Business Name')
    def display_name_with_status(self, obj):
        """Display tenant name with status badge - Unfold compatible"""
        if obj.is_active:
            badge_html = '<span class="badge badge-success">ACTIVE</span>'
        else:
            badge_html = '<span class="badge badge-danger">INACTIVE</span>'
        
        return mark_safe(f'<strong>{obj.name}</strong> {badge_html}')
    
    @display(description='Currency')
    def display_currency(self, obj):
        """Display currency with symbol - Unfold compatible"""
        symbol = getattr(obj, 'currency_symbol', '$')
        currency = getattr(obj, 'currency', 'USD')
        return mark_safe(f'<code>{symbol} {currency}</code>')
    
    def save_model(self, request, obj, form, change):
        """
        Auto-populate currency symbol and owner when saving
        CRITICAL FIX: Sets owner_id to prevent NOT NULL constraint error
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
        
        # FIX: Auto-set owner to current user if not set (for new tenants)
        if not change and not obj.owner_id:  # Only for new objects
            obj.owner = request.user
        
        super().save_model(request, obj, form, change)