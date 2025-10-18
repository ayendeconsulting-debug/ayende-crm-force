"""
Notification Admin for Ayende CRMForce
Django admin interface for managing notifications
"""

from django.contrib import admin
from .models import Notification, NotificationRecipient


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """
    Admin interface for Notification model
    """
    list_display = [
        'title',
        'tenant',
        'category',
        'status',
        'total_recipients',
        'total_read',
        'read_rate',
        'created_at',
    ]
    list_filter = [
        'status',
        'category',
        'priority',
        'created_at',
        'tenant',
    ]
    search_fields = [
        'title',
        'message',
        'tenant__name',
    ]
    readonly_fields = [
        'id',
        'total_recipients',
        'total_delivered',
        'total_read',
        'total_failed',
        'sent_at',
        'created_at',
        'updated_at',
    ]
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'id',
                'tenant',
                'created_by',
                'title',
                'message',
                'category',
                'priority',
            )
        }),
        ('Targeting', {
            'fields': (
                'target_all_customers',
                'target_vip_only',
                'target_min_points',
                'target_max_points',
                'target_specific_customers',
            )
        }),
        ('Status & Scheduling', {
            'fields': (
                'status',
                'scheduled_for',
                'sent_at',
            )
        }),
        ('Statistics', {
            'fields': (
                'total_recipients',
                'total_delivered',
                'total_read',
                'total_failed',
            )
        }),
        ('Metadata', {
            'fields': (
                'notes',
                'created_at',
                'updated_at',
            )
        }),
    )
    filter_horizontal = ['target_specific_customers']
    
    def read_rate(self, obj):
        """Display read rate percentage"""
        return f"{obj.read_rate}%"
    read_rate.short_description = 'Read Rate'


@admin.register(NotificationRecipient)
class NotificationRecipientAdmin(admin.ModelAdmin):
    """
    Admin interface for NotificationRecipient model
    """
    list_display = [
        'notification_title',
        'customer_name',
        'delivery_status',
        'is_read',
        'delivered_at',
        'read_at',
    ]
    list_filter = [
        'delivery_status',
        'is_read',
        'delivered_at',
        'notification__category',
    ]
    search_fields = [
        'notification__title',
        'tenant_customer__customer__first_name',
        'tenant_customer__customer__last_name',
        'tenant_customer__customer__email',
    ]
    readonly_fields = [
        'id',
        'delivered_at',
        'read_at',
        'created_at',
        'updated_at',
    ]
    
    def notification_title(self, obj):
        """Display notification title"""
        return obj.notification.title
    notification_title.short_description = 'Notification'
    
    def customer_name(self, obj):
        """Display customer name"""
        return obj.tenant_customer.customer.get_full_name()
    customer_name.short_description = 'Customer'
