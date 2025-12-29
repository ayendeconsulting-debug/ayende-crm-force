"""
Provisioning Admin
Django admin interface for provisioning management

Location: provisioning/admin.py
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone

from .models import ProvisioningToken, SetupWizardProgress


@admin.register(ProvisioningToken)
class ProvisioningTokenAdmin(admin.ModelAdmin):
    """Admin interface for provisioning tokens"""
    
    list_display = [
        'business_name',
        'subdomain',
        'owner_email',
        'status_badge',
        'created_at',
        'action_buttons',
    ]
    
    list_filter = ['status', 'created_at']
    search_fields = ['business_name', 'subdomain', 'owner_email', 'business_email']
    readonly_fields = [
        'id', 'token', 'signature', 'created_at', 
        'provisioned_at', 'provisioned_by', 'error_message',
    ]
    
    fieldsets = (
        ('Status', {
            'fields': ('status', 'error_message'),
        }),
        ('Business Information', {
            'fields': ('business_name', 'subdomain', 'business_email', 'business_phone'),
        }),
        ('Owner Information', {
            'fields': ('owner_first_name', 'owner_last_name', 'owner_email'),
        }),
        ('Branding', {
            'fields': ('primary_color', 'secondary_color'),
            'classes': ('collapse',),
        }),
        ('Token Details', {
            'fields': ('id', 'token', 'signature', 'created_at', 'expires_at'),
            'classes': ('collapse',),
        }),
        ('Provisioning Result', {
            'fields': ('tenant', 'provisioned_at', 'provisioned_by'),
            'classes': ('collapse',),
        }),
    )
    
    def status_badge(self, obj):
        """Display status as colored badge"""
        colors = {
            'pending': '#f59e0b',
            'completed': '#10b981',
            'expired': '#6b7280',
            'failed': '#ef4444',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 8px; '
            'border-radius: 4px; font-size: 11px; font-weight: 600;">{}</span>',
            color,
            obj.status.upper()
        )
    status_badge.short_description = 'Status'
    
    def action_buttons(self, obj):
        """Display action buttons based on status"""
        if obj.status == 'pending' and not obj.is_expired:
            url = reverse('provisioning:provision_crm') + f'?token={obj.token}&sig={obj.signature}'
            return format_html(
                '<a href="{}" style="background: #10b981; color: white; '
                'padding: 6px 12px; border-radius: 4px; text-decoration: none; '
                'font-size: 12px;">Provision Now</a>',
                url
            )
        elif obj.status == 'completed' and obj.tenant:
            url = reverse('admin:tenants_tenant_change', args=[obj.tenant.id])
            return format_html(
                '<a href="{}" style="background: #3b82f6; color: white; '
                'padding: 6px 12px; border-radius: 4px; text-decoration: none; '
                'font-size: 12px;">View Tenant</a>',
                url
            )
        return '-'
    action_buttons.short_description = 'Actions'
    
    def has_add_permission(self, request):
        return False


@admin.register(SetupWizardProgress)
class SetupWizardProgressAdmin(admin.ModelAdmin):
    """Admin interface for setup wizard progress"""
    
    list_display = [
        'tenant',
        'progress_display',
        'status_badge',
        'created_at',
        'completed_at',
    ]
    
    list_filter = ['step_5_completed', 'created_at']
    search_fields = ['tenant__name', 'tenant__subdomain']
    readonly_fields = [
        'id', 'setup_token', 'setup_token_expires_at',
        'created_at', 'completed_at',
    ]
    
    def progress_display(self, obj):
        """Display step progress"""
        completed = sum([
            obj.step_1_completed,
            obj.step_2_completed,
            obj.step_3_completed,
            obj.step_4_completed,
            obj.step_5_completed,
        ])
        percentage = (completed / 5) * 100
        
        return format_html(
            '<div style="width: 100px; background: #e5e7eb; border-radius: 4px;">'
            '<div style="width: {}%; background: #10b981; height: 20px; text-align: center; '
            'color: white; font-size: 11px; line-height: 20px; border-radius: 4px;">{}/5</div></div>',
            percentage,
            completed
        )
    progress_display.short_description = 'Progress'
    
    def status_badge(self, obj):
        """Display completion status"""
        if obj.is_completed:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 4px 8px; '
                'border-radius: 4px; font-size: 11px;">COMPLETED</span>'
            )
        elif not obj.is_token_valid:
            return format_html(
                '<span style="background: #ef4444; color: white; padding: 4px 8px; '
                'border-radius: 4px; font-size: 11px;">EXPIRED</span>'
            )
        else:
            return format_html(
                '<span style="background: #f59e0b; color: white; padding: 4px 8px; '
                'border-radius: 4px; font-size: 11px;">IN PROGRESS</span>'
            )
    status_badge.short_description = 'Status'
    
    def has_add_permission(self, request):
        return False