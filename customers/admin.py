"""
Admin configuration for Customers app
UPDATED for Multi-Tenant Architecture
WITH Platform Admin Support
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from unfold.admin import ModelAdmin
from .models import Customer, TenantCustomer, Transaction, SyncLog, SystemMapping


class PlatformAdminMixin:
    """
    Mixin to handle platform admin permissions.
    Platform admins bypass all tenant-based restrictions.
    """
    
    def has_view_permission(self, request, obj=None):
        # Platform admins can view everything
        if hasattr(request.user, 'is_platform_admin') and request.user.is_platform_admin:
            return True
        return super().has_view_permission(request, obj)
    
    def has_change_permission(self, request, obj=None):
        # Platform admins can change everything
        if hasattr(request.user, 'is_platform_admin') and request.user.is_platform_admin:
            return True
        return super().has_change_permission(request, obj)
    
    def has_add_permission(self, request):
        # Platform admins can add anything
        if hasattr(request.user, 'is_platform_admin') and request.user.is_platform_admin:
            return True
        return super().has_add_permission(request)
    
    def has_delete_permission(self, request, obj=None):
        # Platform admins can delete anything
        if hasattr(request.user, 'is_platform_admin') and request.user.is_platform_admin:
            return True
        return super().has_delete_permission(request, obj)
    
    def get_queryset(self, request):
        """
        Filter queryset based on user permissions.
        Platform admins see everything, tenant users see only their data.
        """
        qs = super().get_queryset(request)
        
        # Platform admins see all data
        if hasattr(request.user, 'is_platform_admin') and request.user.is_platform_admin:
            return qs
        
        # Let other methods handle tenant filtering
        return qs


@admin.register(Customer)
class CustomerAdmin(PlatformAdminMixin, ModelAdmin):
    """Admin interface for global Customer model (identity only)"""
    
    list_display = [
        'first_name',
        'last_name',
        'created_at',
    ]
    
    search_fields = [
        'first_name',
        'last_name',
    ]
    
    ordering = ['-created_at']
    
    readonly_fields = [
        'id',
        'created_at',
        'updated_at'
    ]
    
    fieldsets = (
        ('Identity', {
            'fields': (
                'id',
                'first_name',
                'last_name',
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at'
            )
        }),
    )


@admin.register(TenantCustomer)
class TenantCustomerAdmin(PlatformAdminMixin, BaseUserAdmin, ModelAdmin):
    """Admin interface for TenantCustomer (authentication + tenant-specific data)"""
    
    list_display = [
        'username',
        'email',
        'get_customer_name',
        'tenant',
        'role',
        'is_active',
        'loyalty_points',
        'date_joined'
    ]
    
    list_filter = [
        'is_active',
        'role',
        'tenant',
        'date_joined',
        'preferred_language',
        'email_notifications'
    ]
    
    search_fields = [
        'username',
        'email',
        'customer__first_name',
        'customer__last_name',
        'tenant__name',
        'notes'
    ]
    
    ordering = ['-date_joined']
    
    readonly_fields = [
        'id',
        'date_joined',
        'last_login',
        'updated_at',
        'joined_at'
    ]
    
    fieldsets = (
        ('Authentication', {
            'fields': (
                'id',
                'username',
                'email',
                'password'
            )
        }),
        ('Customer & Tenant', {
            'fields': (
                'customer',
                'tenant',
                'role'
            )
        }),
        ('Personal Information', {
            'fields': (
                'phone',
                'date_of_birth',
                'profile_picture'
            )
        }),
        ('Address', {
            'fields': (
                'address',
                'city',
                'state',
                'postal_code',
                'country'
            )
        }),
        ('Permissions', {
            'fields': (
                'is_active',
                'is_staff',
                'groups',
                'user_permissions'
            )
        }),
        ('Loyalty Program', {
            'fields': (
                'loyalty_points',
                'loyalty_tier',
                'total_spent',
                'total_purchases',
                'visit_count',
                'last_visit',
                'purchase_count',
                'last_purchase_date',
                'last_purchase_at'
            )
        }),
        ('Preferences', {
            'fields': (
                'preferred_language',
                'marketing_opt_in',
                'email_notifications',
                'sms_notifications',
                'push_notifications'
            )
        }),
        ('Email Verification', {
            'fields': (
                'email_verified',
                'email_verification_token',
                'email_verification_sent_at'
            )
        }),
        ('Business Data', {
            'fields': (
                'is_vip',
                'needs_enrichment',
                'notes',
                'tags'
            )
        }),
        ('Integration', {
            'fields': (
                'external_id',
                'last_synced_at'
            )
        }),
        ('Important Dates', {
            'fields': (
                'date_joined',
                'joined_at',
                'last_login',
                'updated_at'
            )
        }),
    )
    
    add_fieldsets = (
        ('Create New Tenant Customer', {
            'classes': ('wide',),
            'fields': (
                'customer',
                'tenant',
                'username',
                'email',
                'password1',
                'password2',
                'role',
                'is_active',
            ),
        }),
    )
    
    def get_customer_name(self, obj):
        """Display customer full name"""
        return obj.get_full_name()
    get_customer_name.short_description = 'Customer Name'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        qs = super().get_queryset(request)
        return qs.select_related('customer', 'tenant')


@admin.register(Transaction)
class TransactionAdmin(PlatformAdminMixin, ModelAdmin):
    """Admin interface for Transaction model"""
    
    list_display = [
        'transaction_number',
        'tenant',
        'customer_name',
        'total',
        'status',
        'transaction_type',
        'transaction_date'
    ]
    
    list_filter = [
        'status',
        'transaction_type',
        'payment_method',
        'tenant',
        'transaction_date',
        'external_source'
    ]
    
    search_fields = [
        'transaction_number',
        'transaction_id',
        'tenant_customer__username',
        'tenant_customer__email',
        'tenant_customer__customer__first_name',
        'tenant_customer__customer__last_name'
    ]
    
    ordering = ['-transaction_date']
    
    readonly_fields = [
        'transaction_id',
        'created_at',
        'updated_at',
        'synced_at'
    ]
    
    fieldsets = (
        ('Transaction Info', {
            'fields': (
                'transaction_id',
                'transaction_number',
                'receipt_number',
                'tenant',
                'tenant_customer',
                'is_anonymous'
            )
        }),
        ('Financial', {
            'fields': (
                'amount',
                'tax',
                'discount',
                'total',
                'currency',
                'payment_method'
            )
        }),
        ('Loyalty', {
            'fields': (
                'points_earned',
                'points_redeemed'
            )
        }),
        ('Details', {
            'fields': (
                'transaction_type',
                'status',
                'items_description',
                'items',
                'notes'
            )
        }),
        ('Integration', {
            'fields': (
                'external_id',
                'external_source',
                'processed_by',
                'created_by',
                'synced_at'
            )
        }),
        ('Timestamps', {
            'fields': (
                'transaction_date',
                'created_at',
                'updated_at'
            )
        }),
    )


@admin.register(SyncLog)
class SyncLogAdmin(PlatformAdminMixin, ModelAdmin):
    """Admin interface for SyncLog model"""
    
    list_display = [
        'operation',
        'entity_type',
        'entity_id',
        'status',
        'direction',
        'attempt_count',
        'created_at'
    ]
    
    list_filter = [
        'status',
        'direction',
        'entity_type',
        'created_at'
    ]
    
    search_fields = [
        'operation',
        'entity_type',
        'entity_id',
        'error_message'
    ]
    
    ordering = ['-created_at']
    
    readonly_fields = [
        'id',
        'created_at',
        'completed_at'
    ]


@admin.register(SystemMapping)
class SystemMappingAdmin(PlatformAdminMixin, ModelAdmin):
    """Admin interface for SystemMapping model"""
    
    list_display = [
        'entity_type',
        'crm_id',
        'pos_id',
        'tenant',
        'sync_status',
        'last_synced_at'
    ]
    
    list_filter = [
        'entity_type',
        'sync_status',
        'tenant',
        'last_synced_at'
    ]
    
    search_fields = [
        'crm_id',
        'pos_id',
        'tenant__name'
    ]
    
    ordering = ['-created_at']
    
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'last_synced_at'
    ]