"""
Provisioning Views
Handles CRM tenant provisioning from POS and setup wizard

Location: provisioning/views.py
"""

import json
import secrets
import logging
import requests  # ✅ ADDED: For POS webhook
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from django.db import transaction
from django.core.mail import send_mail

from .models import ProvisioningToken, SetupWizardProgress
from dashboard.services.pos_integration import POSIntegrationService
from tenants.models import Tenant, TenantSettings
from customers.models import TenantCustomer

logger = logging.getLogger(__name__)  # ✅ ADDED: Logger


@staff_member_required
@require_GET
def provision_crm(request):
    """
    Process provisioning magic link from admin email.
    Requires Django admin authentication.
    
    URL: /provisioning/provision/?token=xxx&sig=xxx
    """
    token = request.GET.get('token')
    signature = request.GET.get('sig')
    
    if not token or not signature:
        messages.error(request, 'Invalid provisioning link. Missing token or signature.')
        return redirect('admin:index')
    
    # Check if token already processed
    existing = ProvisioningToken.objects.filter(token=token).first()
    if existing:
        if existing.status == 'completed':
            messages.warning(
                request, 
                f'This business has already been provisioned. Tenant: {existing.tenant.name if existing.tenant else "Unknown"}'
            )
            return redirect('admin:provisioning_provisioningtoken_changelist')
        elif existing.status == 'expired':
            messages.error(request, 'This provisioning link has expired.')
            return redirect('admin:provisioning_provisioningtoken_changelist')
    
    # Verify signature
    try:
        if not ProvisioningToken.verify_signature(token, signature):
            messages.error(request, 'Invalid provisioning link. Signature verification failed.')
            return redirect('admin:index')
    except ValueError as e:
        messages.error(request, f'Configuration error: {str(e)}')
        return redirect('admin:index')
    
    # Decode payload
    try:
        payload = ProvisioningToken.decode_payload(token)
    except ValueError as e:
        messages.error(request, f'Invalid provisioning link: {str(e)}')
        return redirect('admin:index')
    
    # Check expiration from payload
    created_at = payload.get('createdAt')
    if created_at:
        from datetime import datetime
        try:
            created_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            if timezone.now() > created_time + timedelta(hours=72):
                messages.error(request, 'This provisioning link has expired (72 hours).')
                return redirect('admin:index')
        except:
            pass
    
    # Check if subdomain already exists
    subdomain = payload.get('subdomain')
    if Tenant.objects.filter(subdomain=subdomain).exists():
        messages.error(
            request, 
            f'A tenant with subdomain "{subdomain}" already exists. Manual intervention required.'
        )
        return redirect('admin:index')
    
    # Create or get provisioning token record
    if not existing:
        existing = ProvisioningToken.create_from_payload(payload, token, signature)
    
    # Render confirmation page
    context = {
        'token': existing,
        'payload': payload,
        'title': f'Provision CRM: {payload.get("businessName")}',
    }
    return render(request, 'provisioning/confirm_provision.html', context)


@staff_member_required
@require_POST
def execute_provision(request):
    """
    Execute the actual provisioning after admin confirms.
    Creates Tenant, TenantSettings, and Owner account.
    
    URL: /provisioning/execute/
    """
    token_id = request.POST.get('token_id')
    
    if not token_id:
        messages.error(request, 'Missing token ID.')
        return redirect('admin:index')
    
    prov_token = get_object_or_404(ProvisioningToken, id=token_id)
    
    # Validate token is still valid
    if not prov_token.is_valid:
        messages.error(request, f'Token is no longer valid. Status: {prov_token.status}')
        return redirect('admin:provisioning_provisioningtoken_changelist')
    
    try:
        with transaction.atomic():
            # 1. Create Tenant
            tenant = Tenant.objects.create(
                name=prov_token.business_name,
                subdomain=prov_token.subdomain,
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
            
            # 3. Create Owner as TenantCustomer with role='owner'
            owner = TenantCustomer.objects.create(
                tenant=tenant,
                email=prov_token.owner_email,
                first_name=prov_token.owner_first_name,
                last_name=prov_token.owner_last_name,
                role='owner',
                is_active=True,
            )
            
            # 4. Set tenant owner reference
            tenant.owner = owner
            tenant.save()
            
            # 5. Create setup wizard progress
            setup_progress = SetupWizardProgress.create_for_tenant(tenant)
            
            # 6. Mark provisioning token as completed
            prov_token.mark_completed(tenant, request.user.email)
            
            # 7. Send setup wizard email to owner
            send_setup_wizard_email(
                owner_email=prov_token.owner_email,
                owner_name=f"{prov_token.owner_first_name} {prov_token.owner_last_name}",
                business_name=prov_token.business_name,
                subdomain=prov_token.subdomain,
                setup_token=setup_progress.setup_token,
            )
        
        # ✅ ADDED: Notify POS that provisioning is complete (AFTER transaction)
        notify_pos_provisioning_complete(
            pos_business_id=prov_token.pos_business_id,
            crm_tenant_id=str(tenant.tenant_uuid),
            subdomain=tenant.subdomain,
        )
        
        messages.success(
            request, 
            f'Successfully provisioned CRM for "{prov_token.business_name}"! '
            f'Setup wizard email sent to {prov_token.owner_email}.'
        )
        return redirect('admin:tenants_tenant_change', tenant.tenant_uuid)
        
    except Exception as e:
        prov_token.mark_failed(str(e))
        messages.error(request, f'Provisioning failed: {str(e)}')
        return redirect('admin:provisioning_provisioningtoken_changelist')


def send_setup_wizard_email(owner_email, owner_name, business_name, subdomain, setup_token):
    """Send setup wizard email to business owner"""
    setup_url = f"https://{subdomain}.ayendecx.com/provisioning/wizard/?token={setup_token}"
    
    subject = f"Complete Your {business_name} CRM Setup"
    
    html_message = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #10B981 0%, #059669 100%); color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }}
            .content {{ background: #f8f9fa; padding: 30px; border-radius: 0 0 8px 8px; }}
            .button {{ display: inline-block; padding: 14px 30px; background: #10B981; color: white !important; text-decoration: none; border-radius: 5px; font-weight: bold; margin: 20px 0; }}
            .steps {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; }}
            .step {{ padding: 10px 0; border-bottom: 1px solid #eee; }}
            .step:last-child {{ border-bottom: none; }}
            .step-number {{ display: inline-block; width: 30px; height: 30px; background: #10B981; color: white; border-radius: 50%; text-align: center; line-height: 30px; margin-right: 10px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Welcome to Ayende-CX CRM!</h1>
                <p style="margin: 0; opacity: 0.9;">Your CRM is ready for setup</p>
            </div>
            
            <div class="content">
                <p>Hi <strong>{owner_name}</strong>,</p>
                
                <p>Great news! Your CRM for <strong>{business_name}</strong> has been provisioned and is ready for setup.</p>
                
                <p>Click the button below to complete your setup wizard:</p>
                
                <p style="text-align: center;">
                    <a href="{setup_url}" class="button">Complete Setup</a>
                </p>
                
                <div class="steps">
                    <h3 style="margin-top: 0;">What you'll set up:</h3>
                    <div class="step">
                        <span class="step-number">1</span>
                        <strong>Verify Business Details</strong>
                    </div>
                    <div class="step">
                        <span class="step-number">2</span>
                        <strong>Set Your Password</strong>
                    </div>
                    <div class="step">
                        <span class="step-number">3</span>
                        <strong>Configure Loyalty Program</strong>
                    </div>
                    <div class="step">
                        <span class="step-number">4</span>
                        <strong>Import Customers</strong> (optional)
                    </div>
                    <div class="step">
                        <span class="step-number">5</span>
                        <strong>Review & Complete</strong>
                    </div>
                </div>
                
                <p style="font-size: 14px; color: #666;">
                    This setup link expires in 7 days.
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    
    plain_message = f"""
Welcome to Ayende-CX CRM!

Hi {owner_name},

Your CRM for {business_name} has been provisioned and is ready for setup.

Complete your setup here: {setup_url}

This link expires in 7 days.
    """
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[owner_email],
            html_message=html_message,
            fail_silently=False,
        )
        print(f"[PROVISIONING] Setup wizard email sent to {owner_email}")
    except Exception as e:
        print(f"[PROVISIONING] Failed to send setup email: {str(e)}")


# ✅ ADDED: Notify POS that provisioning is complete
def notify_pos_provisioning_complete(pos_business_id, crm_tenant_id, subdomain):
    """
    Notify POS that CRM provisioning is complete.
    Updates the POS business record with the CRM tenant UUID.
    
    Args:
        pos_business_id: POS business UUID
        crm_tenant_id: CRM tenant UUID
        subdomain: Business subdomain
    """
    try:
        pos_api_url = getattr(settings, 'POS_API_BASE_URL', 'https://pos-staging.ayendecx.com/api/v1')
        webhook_secret = getattr(settings, 'WEBHOOK_SECRET', None)
        
        if not webhook_secret:
            logger.error("[PROVISIONING] WEBHOOK_SECRET not configured")
            return
        
        webhook_url = f"{pos_api_url}/webhooks/provisioning-complete"
        
        payload = {
            'business_id': pos_business_id,
            'crm_tenant_id': crm_tenant_id,
            'subdomain': subdomain,
        }
        
        headers = {
            'Content-Type': 'application/json',
            'X-Webhook-Secret': webhook_secret,
        }
        
        logger.info(f"[PROVISIONING] Notifying POS: {webhook_url}")
        logger.info(f"[PROVISIONING] Payload: business={pos_business_id}, tenant={crm_tenant_id}")
        
        response = requests.post(
            webhook_url,
            json=payload,
            headers=headers,
            timeout=10,
        )
        
        if response.status_code == 200:
            logger.info(f"[PROVISIONING] POS notified successfully: {subdomain}")
        else:
            logger.error(
                f"[PROVISIONING] POS notification failed: {response.status_code} - {response.text}"
            )
            
    except requests.Timeout:
        logger.error("[PROVISIONING] POS webhook timeout")
    except requests.RequestException as e:
        logger.error(f"[PROVISIONING] POS webhook error: {str(e)}")
    except Exception as e:
        logger.error(f"[PROVISIONING] Unexpected error notifying POS: {str(e)}")


# =============================================================================
# SETUP WIZARD VIEWS
# =============================================================================

def setup_wizard(request):
    """
    Main setup wizard entry point.
    URL: /provisioning/wizard/?token=xxx
    """
    # Rest of the file remains unchanged...
    pass