"""
Provisioning Views
Handles CRM tenant provisioning from POS and setup wizard

Location: provisioning/views.py
"""

import json
import secrets
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
from tenants.models import Tenant, TenantSettings
from customers.models import TenantCustomer


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
        
        messages.success(
            request, 
            f'Successfully provisioned CRM for "{prov_token.business_name}"! '
            f'Setup wizard email sent to {prov_token.owner_email}.'
        )
        return redirect('admin:tenants_tenant_change', tenant.id)
        
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


# =============================================================================
# SETUP WIZARD VIEWS
# =============================================================================

def setup_wizard(request):
    """
    Main setup wizard entry point.
    URL: /provisioning/wizard/?token=xxx
    """
    setup_token = request.GET.get('token')
    
    if not setup_token:
        return render(request, 'provisioning/wizard/error.html', {
            'error': 'Missing setup token. Please use the link from your email.'
        })
    
    try:
        progress = SetupWizardProgress.objects.select_related('tenant').get(
            setup_token=setup_token
        )
    except SetupWizardProgress.DoesNotExist:
        return render(request, 'provisioning/wizard/error.html', {
            'error': 'Invalid setup token. Please contact support.'
        })
    
    if not progress.is_token_valid:
        return render(request, 'provisioning/wizard/error.html', {
            'error': 'This setup link has expired. Please contact support for a new link.'
        })
    
    if progress.is_completed:
        return render(request, 'provisioning/wizard/complete.html', {
            'tenant': progress.tenant,
        })
    
    # Store token in session
    request.session['setup_token'] = setup_token
    request.session['tenant_id'] = str(progress.tenant.id)
    
    # Redirect to current step
    return redirect('provisioning:wizard_step', step=progress.current_step)


def wizard_step(request, step):
    """Handle individual wizard steps (1-5)"""
    setup_token = request.session.get('setup_token')
    
    if not setup_token:
        return redirect('provisioning:setup_wizard')
    
    try:
        progress = SetupWizardProgress.objects.select_related('tenant').get(
            setup_token=setup_token
        )
    except SetupWizardProgress.DoesNotExist:
        return redirect('provisioning:setup_wizard')
    
    tenant = progress.tenant
    
    try:
        tenant_settings = tenant.settings
    except TenantSettings.DoesNotExist:
        tenant_settings = None
    
    try:
        owner = TenantCustomer.objects.get(tenant=tenant, role='owner')
    except TenantCustomer.DoesNotExist:
        owner = None
    
    context = {
        'tenant': tenant,
        'tenant_settings': tenant_settings,
        'owner': owner,
        'progress': progress,
        'current_step': step,
    }
    
    if request.method == 'POST':
        return handle_wizard_step_post(request, step, progress, tenant, owner, tenant_settings)
    
    template_name = f'provisioning/wizard/step_{step}.html'
    return render(request, template_name, context)


def handle_wizard_step_post(request, step, progress, tenant, owner, tenant_settings):
    """Handle POST for each wizard step"""
    
    step = int(step)
    
    if step == 1:
        progress.complete_step(1)
        messages.success(request, 'Business details confirmed!')
        return redirect('provisioning:wizard_step', step=2)
    
    elif step == 2:
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        if not password or len(password) < 8:
            messages.error(request, 'Password must be at least 8 characters.')
            return redirect('provisioning:wizard_step', step=2)
        
        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return redirect('provisioning:wizard_step', step=2)
        
        from django.contrib.auth.hashers import make_password
        owner.password_hash = make_password(password)
        owner.save()
        
        progress.complete_step(2)
        messages.success(request, 'Password set successfully!')
        return redirect('provisioning:wizard_step', step=3)
    
    elif step == 3:
        loyalty_enabled = request.POST.get('loyalty_enabled') == 'on'
        points_per_currency = request.POST.get('points_per_currency', 1)
        points_redemption_rate = request.POST.get('points_redemption_rate', 100)
        welcome_bonus = request.POST.get('welcome_bonus_points', 0)
        
        if tenant_settings:
            tenant_settings.loyalty_enabled = loyalty_enabled
            tenant_settings.points_per_currency = int(points_per_currency)
            tenant_settings.points_redemption_rate = int(points_redemption_rate)
            tenant_settings.welcome_bonus_points = int(welcome_bonus)
            tenant_settings.save()
        
        progress.complete_step(3)
        messages.success(request, 'Loyalty program configured!')
        return redirect('provisioning:wizard_step', step=4)
    
    elif step == 4:
        csv_file = request.FILES.get('customer_csv')
        
        if csv_file:
            try:
                import_result = import_customers_from_csv(csv_file, tenant)
                messages.success(
                    request, 
                    f'Imported {import_result["imported"]} customers. '
                    f'{import_result["skipped"]} skipped.'
                )
            except Exception as e:
                messages.warning(request, f'Import had issues: {str(e)}')
        
        progress.complete_step(4)
        return redirect('provisioning:wizard_step', step=5)
    
    elif step == 5:
        progress.complete_step(5)
        
        if 'setup_token' in request.session:
            del request.session['setup_token']
        if 'tenant_id' in request.session:
            del request.session['tenant_id']
        
        messages.success(request, 'Setup complete! Your CRM is ready to use.')
        return redirect('provisioning:wizard_complete')
    
    return redirect('provisioning:wizard_step', step=step)


def wizard_complete(request):
    """Setup wizard completion page"""
    tenant_id = request.session.get('tenant_id')
    tenant = None
    
    if tenant_id:
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            pass
    
    return render(request, 'provisioning/wizard/complete.html', {
        'tenant': tenant,
    })


def import_customers_from_csv(csv_file, tenant):
    """Import customers from CSV file"""
    import csv
    import io
    
    decoded_file = csv_file.read().decode('utf-8')
    io_string = io.StringIO(decoded_file)
    reader = csv.DictReader(io_string)
    
    imported = 0
    skipped = 0
    
    for row in reader:
        email = row.get('email', '').strip()
        
        if not email:
            skipped += 1
            continue
        
        if TenantCustomer.objects.filter(tenant=tenant, email=email).exists():
            skipped += 1
            continue
        
        try:
            TenantCustomer.objects.create(
                tenant=tenant,
                email=email,
                first_name=row.get('first_name', '').strip(),
                last_name=row.get('last_name', '').strip(),
                phone=row.get('phone', '').strip(),
                role='customer',
                is_active=True,
            )
            imported += 1
        except Exception:
            skipped += 1
    
    return {'imported': imported, 'skipped': skipped}


@staff_member_required
def pending_provisions(request):
    """View pending provisioning requests"""
    pending = ProvisioningToken.objects.filter(status='pending').order_by('-created_at')
    
    context = {
        'pending_tokens': pending,
        'title': 'Pending CRM Provisions',
    }
    return render(request, 'provisioning/pending_list.html', context)