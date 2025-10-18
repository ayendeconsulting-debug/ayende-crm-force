"""
Admin configuration for Tenants app
"""

from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Tenant, TenantSettings


@admin.register(Tenant)
class TenantAdmin(ModelAdmin):
    """Admin interface for Tenant model"""
    
    list_display = [
        'name',
        'slug',
        'subscription_status',
        'customer_count',
        'is_active',
        'created_at'
    ]
    
    list_filter = [
        'subscription_status',
        'is_active',
        'created_at'
    ]
    
    search_fields = [
        'name',
        'slug',
        'business_email',
        'owner__email',
        'owner__first_name',
        'owner__last_name'
    ]
    
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'subdomain_url'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'id',
                'name',
                'slug',
                'description',
                'owner'
            )
        }),
        ('Contact Information', {
            'fields': (
                'business_email',
                'business_phone',
                'business_address',
                'website'
            )
        }),
        ('Branding', {
            'fields': (
                'logo',
                'primary_color',
                'secondary_color'
            )
        }),
        ('Subscription', {
            'fields': (
                'subscription_status',
                'trial_ends_at',
                'subscription_starts_at',
                'subscription_ends_at'
            )
        }),
        ('Limits', {
            'fields': (
                'max_customers',
                'max_storage_gb',
                'max_users'
            )
        }),
        ('Status', {
            'fields': (
                'is_active',
                'subdomain_url',
                'created_at',
                'updated_at'
            )
        }),
    )
    
    def customer_count(self, obj):
        """Display customer count"""
        return obj.customer_count
    customer_count.short_description = 'Customers'


@admin.register(TenantSettings)
class TenantSettingsAdmin(ModelAdmin):
    """Admin interface for TenantSettings model"""
    
    list_display = [
        'tenant',
        'allow_customer_registration',
        'loyalty_points_enabled',
        'enable_email_notifications'
    ]
    
    list_filter = [
        'allow_customer_registration',
        'loyalty_points_enabled',
        'enable_email_notifications'
    ]
    
    search_fields = [
        'tenant__name',
        'tenant__slug'
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at'
    ]