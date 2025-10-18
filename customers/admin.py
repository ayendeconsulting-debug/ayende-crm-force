"""
Admin configuration for Customers app
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from unfold.admin import ModelAdmin
from .models import Customer, TenantCustomer


@admin.register(Customer)
class CustomerAdmin(BaseUserAdmin, ModelAdmin):
    """Admin interface for Customer model"""
    
    list_display = [
        'email',
        'first_name',
        'last_name',
        'phone',
        'is_active',
        'is_staff',
        'date_joined'
    ]
    
    list_filter = [
        'is_active',
        'is_staff',
        'is_superuser',
        'date_joined',
        'preferred_language'
    ]
    
    search_fields = [
        'email',
        'first_name',
        'last_name',
        'phone'
    ]
    
    ordering = ['-date_joined']
    
    readonly_fields = [
        'id',
        'date_joined',
        'last_login',
        'updated_at'
    ]
    
    fieldsets = (
        ('Authentication', {
            'fields': (
                'id',
                'email',
                'password'
            )
        }),
        ('Personal Information', {
            'fields': (
                'first_name',
                'last_name',
                'phone',
                'date_of_birth',
                'profile_picture'
            )
        }),
        ('Address', {
            'fields': (
                'address',
                'city',
                'postal_code',
                'country'
            )
        }),
        ('Permissions', {
            'fields': (
                'is_active',
                'is_staff',
                'is_superuser',
                'groups',
                'user_permissions'
            )
        }),
        ('Preferences', {
            'fields': (
                'preferred_language',
            )
        }),
        ('Important Dates', {
            'fields': (
                'date_joined',
                'last_login',
                'updated_at'
            )
        }),
    )
    
    add_fieldsets = (
        ('Create New Customer', {
            'classes': ('wide',),
            'fields': (
                'email',
                'password1',
                'password2',
                'first_name',
                'last_name',
                'phone',
                'is_active',
                'is_staff'
            ),
        }),
    )


@admin.register(TenantCustomer)
class TenantCustomerAdmin(ModelAdmin):
    """Admin interface for TenantCustomer relationship"""
    
    list_display = [
        'customer',
        'tenant',
        'role',
        'loyalty_points',
        'total_purchases',
        'is_vip',
        'is_active',
        'joined_at'
    ]
    
    list_filter = [
        'role',
        'is_active',
        'is_vip',
        'email_notifications',
        'joined_at',
        'tenant'
    ]
    
    search_fields = [
        'customer__email',
        'customer__first_name',
        'customer__last_name',
        'tenant__name',
        'notes'
    ]
    
    readonly_fields = [
        'id',
        'joined_at',
        'updated_at'
    ]
    
    fieldsets = (
        ('Relationship', {
            'fields': (
                'id',
                'customer',
                'tenant',
                'role'
            )
        }),
        ('Customer Data', {
            'fields': (
                'loyalty_points',
                'total_purchases',
                'purchase_count',
                'last_purchase_at'
            )
        }),
        ('Preferences', {
            'fields': (
                'email_notifications',
                'sms_notifications',
                'push_notifications'
            )
        }),
        ('Management', {
            'fields': (
                'notes',
                'tags',
                'is_vip',
                'is_active'
            )
        }),
        ('Timestamps', {
            'fields': (
                'joined_at',
                'updated_at'
            )
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        qs = super().get_queryset(request)
        return qs.select_related('customer', 'tenant')