"""
Django Admin Configuration for Rewards
"""

from django.contrib import admin
from .models import Reward, Redemption, RewardCategory


@admin.register(Reward)
class RewardAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'tenant',
        'reward_type',
        'points_required',
        'status',
        'stock_remaining',
        'redeemed_count',
        'is_featured',
        'created_at'
    ]
    list_filter = [
        'status',
        'reward_type',
        'is_featured',
        'has_stock_limit',
        'has_expiration'
    ]
    search_fields = ['name', 'description', 'tenant__name']
    readonly_fields = ['id', 'redeemed_count', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'id',
                'tenant',
                'name',
                'description',
                'reward_type',
                'image'
            )
        }),
        ('Points & Discounts', {
            'fields': (
                'points_required',
                'discount_type',
                'discount_value',
                'minimum_purchase'
            )
        }),
        ('Stock Management', {
            'fields': (
                'has_stock_limit',
                'total_stock',
                'redeemed_count'
            )
        }),
        ('Expiration & Limits', {
            'fields': (
                'has_expiration',
                'expires_at',
                'limit_per_customer',
                'validity_days'
            )
        }),
        ('Status & Display', {
            'fields': (
                'status',
                'is_featured',
                'display_order'
            )
        }),
        ('Terms & Conditions', {
            'fields': ('terms_conditions',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': (
                'created_by',
                'created_at',
                'updated_at'
            ),
            'classes': ('collapse',)
        })
    )


@admin.register(Redemption)
class RedemptionAdmin(admin.ModelAdmin):
    list_display = [
        'redemption_code',
        'customer',
        'reward',
        'points_spent',
        'status',
        'redeemed_at',
        'is_valid',
        'used_at'
    ]
    list_filter = [
        'status',
        'redeemed_at',
        'used_at'
    ]
    search_fields = [
        'redemption_code',
        'customer__first_name',
        'customer__last_name',
        'customer__email',
        'reward__name'
    ]
    readonly_fields = [
        'id',
        'redemption_code',
        'redeemed_at',
        'updated_at'
    ]
    
    fieldsets = (
        ('Redemption Information', {
            'fields': (
                'id',
                'redemption_code',
                'reward',
                'customer',
                'tenant_customer',
                'tenant'
            )
        }),
        ('Points & Status', {
            'fields': (
                'points_spent',
                'status'
            )
        }),
        ('Validity Period', {
            'fields': (
                'valid_from',
                'valid_until'
            )
        }),
        ('Usage', {
            'fields': (
                'used_at',
                'used_by_staff',
                'transaction'
            )
        }),
        ('Notes', {
            'fields': (
                'customer_note',
                'staff_note',
                'rejection_reason'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': (
                'redeemed_at',
                'updated_at'
            ),
            'classes': ('collapse',)
        })
    )
    
    actions = ['approve_redemptions', 'mark_as_used', 'cancel_redemptions']
    
    def approve_redemptions(self, request, queryset):
        updated = queryset.filter(status='pending').update(status='approved')
        self.message_user(request, f'{updated} redemption(s) approved.')
    approve_redemptions.short_description = 'Approve selected redemptions'
    
    def mark_as_used(self, request, queryset):
        count = 0
        for redemption in queryset.filter(status__in=['pending', 'approved']):
            redemption.use(staff_member=request.user)
            count += 1
        self.message_user(request, f'{count} redemption(s) marked as used.')
    mark_as_used.short_description = 'Mark selected as used'
    
    def cancel_redemptions(self, request, queryset):
        count = 0
        for redemption in queryset.filter(status__in=['pending', 'approved']):
            redemption.cancel(refund_points=True)
            count += 1
        self.message_user(request, f'{count} redemption(s) cancelled with points refunded.')
    cancel_redemptions.short_description = 'Cancel and refund points'


@admin.register(RewardCategory)
class RewardCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'tenant', 'display_order', 'is_active', 'created_at']
    list_filter = ['is_active', 'tenant']
    search_fields = ['name', 'description']
    filter_horizontal = ['rewards']
