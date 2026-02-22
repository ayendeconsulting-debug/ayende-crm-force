"""
Provisioning Admin - Enhanced with Link Regeneration
Django admin interface for provisioning management

Location: provisioning/admin.py
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.contrib import messages
from django.shortcuts import redirect
from datetime import timedelta
import secrets

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
    actions = ['reset_to_pending', 'provision_directly']

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
            url = reverse('admin:tenants_tenant_change', args=[obj.tenant.tenant_uuid])
            return format_html(
                '<a href="{}" style="background: #3b82f6; color: white; '
                'padding: 6px 12px; border-radius: 4px; text-decoration: none; '
                'font-size: 12px;">View Tenant</a>',
                url
            )
        elif obj.status in ['expired', 'failed']:
            return format_html(
                '<span style="color: #6b7280; font-size: 12px;">Use "Reset to Pending" action</span>'
            )
        return '-'
    action_buttons.short_description = 'Actions'

    def reset_to_pending(self, request, queryset):
        """Reset failed/expired tokens to pending status for retry"""
        count = 0
        for token in queryset:
            if token.status in ['expired', 'failed']:
                token.status = 'pending'
                token.expires_at = timezone.now() + timedelta(hours=72)
                token.error_message = None
                token.save()
                count += 1
        
        self.message_user(
            request,
            f'Reset {count} token(s) to pending status with new 72-hour expiration.',
            messages.SUCCESS
        )
    reset_to_pending.short_description = 'Reset selected to Pending (for retry)'

    def provision_directly(self, request, queryset):
        """
        Provision tenant directly from admin panel (bypasses broken links)
        Works even when token/signature is corrupted
        """
        from django.db import transaction
        from tenants.models import Tenant, TenantSettings
        from customers.models import TenantCustomer
        from .views import send_setup_wizard_email
        
        provisioned = 0
        skipped = 0
        errors = []
        
        for prov_token in queryset:
            # Validate token is pending
            if not prov_token.is_valid:
                skipped += 1
                errors.append(f"{prov_token.business_name}: Status is {prov_token.status}")
                continue
            
            # Check if subdomain already exists
            if Tenant.objects.filter(subdomain=prov_token.subdomain).exists():
                skipped += 1
                errors.append(f"{prov_token.business_name}: Subdomain already exists")
                continue
            
            try:
                with transaction.atomic():
                    # 1. Create Tenant
                    tenant = Tenant.objects.create(
                        name=prov_token.business_name,
                        subdomain=prov_token.subdomain,
                        email=prov_token.business_email,
                        phone=prov_token.business_phone or '',
                        is_active=True,
                    )
                    
                    # 2. Create TenantSettings
                    TenantSettings.objects.create(
                        tenant=tenant,
                        primary_color=prov_token.primary_color,
                        secondary_color=prov_token.secondary_color,
                        loyalty_enabled=True,
                        points_per_currency=1,
                        points_redemption_rate=100,
                        welcome_bonus_points=0,
                        pos_sync_enabled=True,
                        pos_api_url='https://pos-staging.ayendecx.com/api/v1',
                    )
                    
                    # 3. Create Owner
                    owner = TenantCustomer.objects.create(
                        tenant=tenant,
                        email=prov_token.owner_email,
                        first_name=prov_token.owner_first_name,
                        last_name=prov_token.owner_last_name,
                        role='owner',
                        is_active=True,
                    )
                    
                    # 4. Set tenant owner
                    tenant.owner = owner
                    tenant.save()
                    
                    # 5. Create setup wizard
                    setup_progress = SetupWizardProgress.create_for_tenant(tenant)
                    
                    # 6. Mark completed
                    prov_token.mark_completed(tenant, request.user.email)
                    
                    # 7. Send setup email
                    send_setup_wizard_email(
                        owner_email=prov_token.owner_email,
                        owner_name=f"{prov_token.owner_first_name} {prov_token.owner_last_name}",
                        business_name=prov_token.business_name,
                        subdomain=prov_token.subdomain,
                        setup_token=setup_progress.setup_token,
                    )
                    
                    provisioned += 1
                    
            except Exception as e:
                prov_token.mark_failed(str(e))
                errors.append(f"{prov_token.business_name}: {str(e)}")
                skipped += 1
        
        # Show results
        if provisioned > 0:
            self.message_user(
                request,
                f'Successfully provisioned {provisioned} tenant(s)!',
                messages.SUCCESS
            )
        
        if skipped > 0:
            error_msg = f'Skipped {skipped} token(s). Check individual records for details.'
            self.message_user(request, error_msg, messages.WARNING)
    
    provision_directly.short_description = 'Provision CRM Directly (bypasses broken links)'
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
        'action_buttons',
    ]

    list_filter = ['step_5_completed', 'created_at']
    search_fields = ['tenant__name', 'tenant__subdomain']
    readonly_fields = [
        'id', 'setup_token', 'setup_token_expires_at',
        'created_at', 'completed_at',
    ]
    actions = ['regenerate_setup_links', 'resend_setup_emails']

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

    def action_buttons(self, obj):
        """Display action buttons"""
        if not obj.is_completed:
            setup_url = reverse('provisioning:setup_wizard') + f'?token={obj.setup_token}'
            return format_html(
                '<a href="{}" target="_blank" style="background: #3b82f6; color: white; '
                'padding: 6px 12px; border-radius: 4px; text-decoration: none; '
                'font-size: 12px;">Open Wizard</a>',
                setup_url
            )
        return '-'
    action_buttons.short_description = 'Actions'

    def regenerate_setup_links(self, request, queryset):
        """Regenerate setup wizard tokens for expired/broken links"""
        count = 0
        for progress in queryset:
            if not progress.is_completed:
                # Generate new token
                progress.setup_token = secrets.token_urlsafe(32)
                progress.setup_token_expires_at = timezone.now() + timedelta(days=7)
                progress.save()
                count += 1
        
        self.message_user(
            request,
            f'Regenerated setup links for {count} tenant(s). Use "Resend Setup Emails" to notify owners.',
            messages.SUCCESS
        )
    regenerate_setup_links.short_description = 'Regenerate Setup Links (new tokens)'

    def resend_setup_emails(self, request, queryset):
        """Resend setup wizard emails with current valid links"""
        from .views import send_setup_wizard_email
        
        sent = 0
        failed = 0
        
        for progress in queryset:
            if not progress.is_completed and progress.is_token_valid:
                try:
                    tenant = progress.tenant
                    owner = tenant.tenantcustomer_set.filter(role='owner').first()
                    
                    if owner:
                        send_setup_wizard_email(
                            owner_email=owner.email,
                            owner_name=f"{owner.first_name} {owner.last_name}",
                            business_name=tenant.name,
                            subdomain=tenant.subdomain,
                            setup_token=progress.setup_token,
                        )
                        sent += 1
                    else:
                        failed += 1
                except Exception as e:
                    failed += 1
                    print(f"Failed to send email: {str(e)}")
        
        if sent > 0:
            self.message_user(
                request,
                f'Sent {sent} setup wizard email(s). {failed} failed.',
                messages.SUCCESS if failed == 0 else messages.WARNING
            )
        else:
            self.message_user(
                request,
                'No valid setup wizards to send emails for.',
                messages.WARNING
            )
    resend_setup_emails.short_description = 'Resend Setup Wizard Emails'

    def has_add_permission(self, request):
        return False

