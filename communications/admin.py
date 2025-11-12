"""
Django Admin Configuration for Communications App
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import Message, MarketingCampaign, Notification, MessageTemplate


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['subject', 'sender_name', 'receiver_name', 'message_type', 'status_badge', 'created_at']
    list_filter = ['message_type', 'status', 'created_at', 'tenant']
    search_fields = ['subject', 'body', 'sender_customer__email', 'receiver_customer__email']
    readonly_fields = ['sent_at', 'delivered_at', 'read_at', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'message_type', 'subject', 'body', 'priority')
        }),
        ('Participants', {
            'fields': ('sender_customer', 'receiver_customer')
        }),
        ('Status', {
            'fields': ('status', 'sent_at', 'delivered_at', 'read_at')
        }),
        ('Campaign & Threading', {
            'fields': ('campaign', 'parent_message'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'draft': '#6b7280',
            'sent': '#3b82f6',
            'delivered': '#10b981',
            'read': '#059669',
            'archived': '#94a3b8',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 12px; border-radius: 12px; font-size: 0.75rem; font-weight: 600;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def sender_name(self, obj):
        return obj.sender_name
    sender_name.short_description = 'From'
    
    def receiver_name(self, obj):
        return obj.receiver_name
    receiver_name.short_description = 'To'


@admin.register(MarketingCampaign)
class MarketingCampaignAdmin(admin.ModelAdmin):
    list_display = ['name', 'target_audience', 'status_badge', 'total_recipients', 'open_rate_display', 'created_at']
    list_filter = ['status', 'target_audience', 'created_at', 'tenant']
    search_fields = ['name', 'subject', 'body']
    readonly_fields = ['total_recipients', 'total_sent', 'total_delivered', 'total_read', 'sent_at', 'completed_at', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Campaign Details', {
            'fields': ('tenant', 'name', 'subject', 'body')
        }),
        ('Targeting', {
            'fields': ('target_audience', 'custom_filter')
        }),
        ('Status & Scheduling', {
            'fields': ('status', 'scheduled_at', 'sent_at', 'completed_at')
        }),
        ('Analytics', {
            'fields': ('total_recipients', 'total_sent', 'total_delivered', 'total_read'),
            'classes': ('collapse',)
        }),
        ('Created By', {
            'fields': ('created_by',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['send_campaign_action']
    
    def status_badge(self, obj):
        colors = {
            'draft': '#6b7280',
            'scheduled': '#fbbf24',
            'sending': '#3b82f6',
            'sent': '#10b981',
            'completed': '#059669',
            'canceled': '#ef4444',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 12px; border-radius: 12px; font-size: 0.75rem; font-weight: 600;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def open_rate_display(self, obj):
        return f"{obj.open_rate:.1f}%"
    open_rate_display.short_description = 'Open Rate'
    
    def send_campaign_action(self, request, queryset):
        sent_count = 0
        for campaign in queryset:
            if campaign.status == 'draft':
                campaign.send_campaign()
                sent_count += 1
        
        self.message_user(request, f"{sent_count} campaign(s) sent successfully.")
    send_campaign_action.short_description = "Send selected campaigns"


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'customer', 'notification_type', 'is_read_badge', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at', 'tenant']
    search_fields = ['title', 'message', 'customer__email', 'customer__first_name', 'customer__last_name']
    readonly_fields = ['read_at', 'created_at']
    
    fieldsets = (
        ('Notification Details', {
            'fields': ('tenant', 'customer', 'notification_type', 'title', 'message')
        }),
        ('Status', {
            'fields': ('is_read', 'read_at')
        }),
        ('Links', {
            'fields': ('link_url', 'related_message'),
            'classes': ('collapse',)
        }),
        ('Timestamp', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def is_read_badge(self, obj):
        if obj.is_read:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 4px 12px; border-radius: 12px; font-size: 0.75rem; font-weight: 600;">Read</span>'
            )
        else:
            return format_html(
                '<span style="background: #3b82f6; color: white; padding: 4px 12px; border-radius: 12px; font-size: 0.75rem; font-weight: 600;">Unread</span>'
            )
    is_read_badge.short_description = 'Status'


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'template_type', 'is_active_badge', 'tenant', 'created_at']
    list_filter = ['template_type', 'is_active', 'tenant', 'created_at']
    search_fields = ['name', 'subject', 'body']
    
    fieldsets = (
        ('Template Details', {
            'fields': ('tenant', 'name', 'template_type')
        }),
        ('Content', {
            'fields': ('subject', 'body')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 4px 12px; border-radius: 12px; font-size: 0.75rem; font-weight: 600;">Active</span>'
            )
        else:
            return format_html(
                '<span style="background: #6b7280; color: white; padding: 4px 12px; border-radius: 12px; font-size: 0.75rem; font-weight: 600;">Inactive</span>'
            )
    is_active_badge.short_description = 'Status'
