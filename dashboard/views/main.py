from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Sum, Q, Count, Avg
from django.http import JsonResponse
from customers.models import Transaction, Customer, TenantCustomer, RentalContract
from customers.authentication import get_tenant_from_request  # PHASE 4: Added import
from tenants.models import Tenant
from datetime import datetime, timedelta
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe
from django.conf import settings
from django.contrib.auth.views import (
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView,
)
from django.urls import reverse_lazy
from django.contrib.auth.forms import PasswordResetForm
from django.utils import timezone
from django.db import models
from notifications.models import Message, NotificationRecipient, Notification
from customers.authentication import get_tenant_from_request

# Import forms used in views
from dashboard.forms import (
    CustomerRegistrationForm,
    CustomerLoginForm,
    BusinessCustomerAddForm,
    BusinessCustomerEditForm,
    CustomerNotesForm,
)
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import send_mail
# ============================================
# INTEGRATION: REST Framework imports
# ============================================
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from dashboard.authentication import IntegrationJWTAuthentication

# Additional imports
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import json
import logging

logger = logging.getLogger(__name__)


# ============================================
# API ENDPOINT: Check Customer by Phone
# ============================================
@require_http_methods(["GET"])
@require_http_methods(["GET"])
def check_customer_by_phone(request):
    """
    API endpoint to check if customer exists by phone number
    Updated to use JWT authentication for POS integration
    """
    # Import verify_jwt_token function
    from dashboard.views.sync_views import verify_jwt_token
    from tenants.models import Tenant
    
    # Verify JWT authentication
    is_valid, payload_or_error, tenant_id = verify_jwt_token(request)
    if not is_valid:
        logger.warning(f"Authentication failed: {payload_or_error}")
        return JsonResponse({
            'success': False,
            'error': f'Authentication failed: {payload_or_error}'
        }, status=401)
    
    # Get tenant from JWT token
    try:
        tenant = Tenant.objects.get(tenant_uuid=tenant_id)
    except Tenant.DoesNotExist:
        logger.error(f"Tenant not found: {tenant_id}")
        return JsonResponse({
            'success': False,
            'error': f'Tenant not found: {tenant_id}'
        }, status=404)
    
    # Get phone from query parameter
    phone = request.GET.get('phone')
    if not phone:
        return JsonResponse({'error': 'Phone number required'}, status=400)
    
    # Search for customer by phone in this tenant
    try:
        customer = TenantCustomer.objects.get(tenant=tenant, phone=phone)
        return JsonResponse({
            'exists': True,
            'customer': {
                'id': str(customer.id),
                'email': customer.email,
                'firstName': customer.first_name,
                'lastName': customer.last_name,
                'phone': customer.phone,
                'loyaltyPoints': customer.loyalty_points
            }
        })
    except TenantCustomer.DoesNotExist:
        return JsonResponse({
            'exists': False
        })
    except Exception as e:
        logger.error(f"Error checking customer by phone: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


# ============================================
# PUBLIC VIEWS
# ============================================
def landing_page(request):
    """
    Public landing page view - accessible to everyone
    Shows tenant-specific branding if accessed via tenant subdomain
    """
    # Get current tenant from middleware
    tenant = getattr(request, 'tenant', None)
    
    # If no tenant, show generic landing page (main site)
    if not tenant:
        return render(request, 'landing.html', {
            'is_main_site': True,
            'site_name': 'Ayende CX',
            'tagline': 'CRM Software Solutions',
        })
    
    # Tenant-specific landing page with branding
    context = {
        'tenant': tenant,
        'is_main_site': False,
        'business_name': tenant.name,
        'business_description': tenant.description or f"Welcome to {tenant.name}",
        'primary_color': tenant.primary_color,
        'secondary_color': tenant.secondary_color,
        'currency_symbol': tenant.currency_symbol,
        'logo_url': tenant.logo.url if tenant.logo else None,
        
        # Navigation settings
        'show_register': tenant.settings.allow_customer_registration if hasattr(tenant, 'settings') else True,
        'show_login': True,
    }
    
    return render(request, 'tenant_landing.html', context)


# Check if Transaction model exists
try:
    from customers.models import Transaction
    TRANSACTIONS_ENABLED = True
except ImportError:
    TRANSACTIONS_ENABLED = False


# ============================================
# AUTHENTICATION VIEWS - PHASE 4 UPDATED
# ============================================
def customer_register(request):
    """
    Customer self-registration view with email verification.
    Customer must verify email before they can login.
    Multi-tenant: Creates TenantCustomer with username format email.subdomain
    """
    # Redirect if already logged in
    if request.user.is_authenticated:
     return redirect('dashboard:dashboard')
    
    # Get tenant from middleware
    tenant = get_tenant_from_request(request)
    
    if not tenant:
        messages.error(request, 'Unable to identify business. Please check the URL.')
        return redirect('/')

    # Check if tenant allows customer registration (skip if settings don't exist)
    try:
        if hasattr(tenant, 'settings') and not tenant.settings.allow_customer_registration:
            messages.error(request, 'Customer registration is currently disabled for this business.')
            return redirect('dashboard:login')
    except AttributeError:
        # Settings don't exist, allow registration
        pass

    if request.method == 'POST':
        # Get form data
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        phone = request.POST.get('phone', '')
        username = request.POST.get('username')  # Generated by template: email.subdomain

        # Validation
        errors = []

        if not all([email, first_name, last_name, password, password_confirm, username]):
            errors.append('All required fields must be filled.')

        if password != password_confirm:
            errors.append('Passwords do not match.')

        if len(password) < 8:
            errors.append('Password must be at least 8 characters long.')

        # Check if username exists for this tenant
        if TenantCustomer.objects.filter(tenant=tenant, username=username).exists():
            errors.append('An account with this email already exists for this business.')

        # Check if email exists for this tenant (additional check)
        if TenantCustomer.objects.filter(tenant=tenant, email=email).exists():
            errors.append('An account with this email already exists for this business.')

        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'dashboard/register.html', {
                'tenant': tenant,
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
                'phone': phone,
            })

        try:
            # Create TenantCustomer with actual form data (NOT placeholder values)
            tenant_customer = TenantCustomer.objects.create(
                tenant=tenant,
                customer=None,  # Bypassed due to schema mismatch
                username=username,        # ✅ From form (email.subdomain format)
                email=email,              # ✅ From form
                first_name=first_name,    # ✅ From form
                last_name=last_name,      # ✅ From form
                phone=phone,              # ✅ From form
                role='customer',
                is_active=False,          # Requires email verification
                email_verified=False,
                is_staff=False,
                is_superuser=False,
            )
            
            # Set password (hashes it automatically)
            tenant_customer.set_password(password)
            tenant_customer.save()

            # Generate verification token
            tenant_customer.generate_verification_token()
            tenant_customer.save()

            # Send verification email with correct parameter order: (tenant_customer, tenant, request)
            send_verification_email(tenant_customer, tenant, request)

            messages.success(
                request,
                'Registration successful! Please check your email to verify your account.'
            )
            return redirect('dashboard:login')

        except Exception as e:
            # Log the error with full traceback
            logger.error(f"Registration error for {email}: {str(e)}", exc_info=True)
            
            messages.error(request, 'An error occurred during registration. Please try again.')
            return render(request, 'dashboard/register.html', {
                'tenant': tenant,
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
                'phone': phone,
            })

    # GET request - show registration form
    return render(request, 'dashboard/register.html', {'tenant': tenant})


def send_verification_email(tenant_customer, tenant, request):
    """
    Send verification email to tenant customer
    Updated for Phase 2/4: Uses TenantCustomer instead of Customer
    """
    # Build verification URL
    verification_url = request.build_absolute_uri(
        f'/verify-email/{tenant_customer.email_verification_token}/'
    )

    # Email context
    context = {
        'customer': tenant_customer,
        'tenant': tenant,
        'verification_url': verification_url,
        'business_name': tenant.name,
    }

    # Render email templates
    html_message = render_to_string('emails/verify_email.html', context)
    plain_message = strip_tags(html_message)

    # Send email
    subject = f'Verify your email - {tenant.name}'
    from_email = settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@ayendecx.com'

    send_mail(
        subject=subject,
        message=plain_message,
        from_email=from_email,
        recipient_list=[tenant_customer.email],
        html_message=html_message,
        fail_silently=False,
    )


def verify_email(request, token):
    """
    Verify email address using token
    Updated for Phase 2/4: Uses TenantCustomer
    """
    tenant = get_tenant_from_request(request)
    
    if not tenant:
        messages.error(request, 'Unable to identify business.')
        return redirect('/')
    
    try:
        tenant_customer = TenantCustomer.objects.get(
            tenant=tenant,
            email_verification_token=token
        )
        
        # Check if token is expired (24 hours)
        if tenant_customer.email_verification_sent_at:
            from django.utils import timezone
            expiry_time = tenant_customer.email_verification_sent_at + timedelta(hours=24)
            if timezone.now() > expiry_time:
                messages.error(request, 'Verification link has expired.')
                return redirect('dashboard:login')
        
        # Verify email
        tenant_customer.email_verified = True
        tenant_customer.is_active = True
        tenant_customer.email_verification_token = None
        tenant_customer.save()
        
        messages.success(request, 'Email verified successfully! You can now log in.')
        return redirect('dashboard:login')
        
    except TenantCustomer.DoesNotExist:
        messages.error(request, 'Invalid verification link.')
        return redirect('dashboard:login')


def resend_verification_email(request):
    """
    Resend verification email to customer
    """
    if request.method == 'POST':
        email = request.POST.get('email')
        tenant = get_tenant_from_request(request)
        
        if not tenant:
            messages.error(request, 'Unable to identify business.')
            return redirect('/')
        
        try:
            tenant_customer = TenantCustomer.objects.get(tenant=tenant, email=email)
            
            if tenant_customer.email_verified:
                messages.info(request, 'Your email is already verified. You can log in.')
                return redirect('dashboard:login')
            
            # Generate new token and send email
            tenant_customer.generate_verification_token()
            tenant_customer.save()
            send_verification_email(tenant_customer, tenant, request)
            
            messages.success(request, 'Verification email has been resent. Please check your inbox.')
            return redirect('dashboard:login')
            
        except TenantCustomer.DoesNotExist:
            messages.error(request, 'No account found with this email address.')
            return redirect('dashboard:register')
    
    return render(request, 'dashboard/resend_verification.html')


def customer_login_view(request):
    """
    Customer login view - handles authentication and tenant verification
    Updated for Phase 2/4: Uses username (email.subdomain) for authentication
    """
    # Redirect if already logged in
    if request.user.is_authenticated:
        return redirect('dashboard:dashboard')
    
    # Get tenant from middleware
    tenant = get_tenant_from_request(request)
    
    if not tenant:
        messages.error(request, 'Unable to identify business. Please check the URL.')
        return redirect('/')

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        username = request.POST.get('username')  # Generated by template: email.subdomain
        
        if not username:
            # Fallback: generate username if template didn't send it
            username = f"{email}.{tenant.subdomain}"
        
        # Authenticate using username (email.subdomain format)
        user = authenticate(request, username=username, password=password, tenant=tenant)
        
        if user is not None:
            # Check if email is verified
            if not user.email_verified:
                messages.error(
                    request,
                    'Please verify your email address before logging in. Check your inbox for the verification link.'
                )
                messages.info(
                    request,
                    mark_safe(
                        'Didn\'t receive the email? '
                        '<a href="/resend-verification/" class="text-blue-500 underline">Click here to resend</a>'
                    )
                )
                return render(request, 'dashboard/login.html', {
                    'tenant': tenant,
                    'form': {'email': {'value': email}}
                })
            
            # Check if user is active
            if not user.is_active:
                messages.error(request, 'Your account is inactive. Please contact support.')
                return render(request, 'dashboard/login.html', {
                    'tenant': tenant,
                    'form': {'email': {'value': email}}
                })
            
            # Login user
            login(request, user)
            messages.success(request, f'Welcome back, {user.get_full_name()}!')
            
            # Check for next parameter
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            
            # Role-based redirect
            # Platform admins go to Django admin
            if getattr(user, 'is_platform_admin', False):
                return redirect('/admin/')

            # Tenant admins/owners/managers/staff go to reports
            if user.role in ['owner', 'admin', 'manager', 'staff']:
                return redirect('/reports/')

            # Customers go to customer dashboard
            return redirect('/dashboard/')
        else:
            messages.error(request, 'Invalid email or password.')
    
    # GET request
    context = {
        'tenant': tenant,
        'form': {}
    }
    return render(request, 'dashboard/login.html', context)


def customer_logout_view(request):
    """
    Customer logout view
    """
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('dashboard:login')


# ============================================
# CUSTOMER DASHBOARD - PHASE 4: Using TenantCustomer
# ============================================
@login_required
def dashboard_redirect(request):
    """
    Smart redirect based on user role.
    This should be the root dashboard URL.
    """
    user = request.user
    
    # Platform admins go to Django admin
    if getattr(user, 'is_platform_admin', False):
        return redirect('/admin/')
    
    # Tenant admins/owners/managers/staff go to reports
    if user.role in ['owner', 'admin', 'manager', 'staff']:
        return redirect('/reports/')
    
    # Customers go to customer dashboard
    return redirect('/dashboard/')

@login_required
def dashboard_home(request):
    """
    Enhanced customer dashboard home page
    Shows customer's transactions, loyalty points, profile summary, and unread counts
    """
    tenant = get_tenant_from_request(request)
    
    # Platform admins should use Django admin
    if getattr(request.user, 'is_platform_admin', False):
        return redirect('/admin/')
    
    if not tenant:
        messages.error(request, 'Unable to identify business.')
        return redirect('/')
    
    # Get TenantCustomer for current user
    tenant_customer = request.user
    
    # Get recent transactions
    recent_transactions = Transaction.objects.filter(
        tenant=tenant,
        tenant_customer=tenant_customer
    ).order_by('-transaction_date')[:10]
    
    # Calculate stats
    total_transactions = Transaction.objects.filter(
        tenant=tenant,
        tenant_customer=tenant_customer
    ).count()
    
    # Get unread messages count (customer_to_business + business_to_customer)
    unread_messages = 0
    unread_notifications = 0
    
    try:
        from notifications.models import Message, NotificationRecipient
        
        unread_messages = Message.objects.filter(
            tenant=tenant,
            status__in=['sent', 'delivered']
        ).filter(
            Q(sender=tenant_customer) | Q(receiver=tenant_customer) | Q(receiver__isnull=True, message_type='business_to_customer')
        ).count()
        
        unread_notifications = NotificationRecipient.objects.filter(
            tenant_customer=tenant_customer,
            is_read=False
        ).count()
    except Exception as e:
        # Models don't exist yet or other error - that's okay, default to 0
        pass
    
    context = {
        'tenant': tenant,
        'customer': tenant_customer,
        'recent_transactions': recent_transactions,
        'total_transactions': total_transactions,
        'loyalty_points': tenant_customer.loyalty_points,
        'total_spent': tenant_customer.total_spent,
        'unread_messages': unread_messages,
        'unread_notifications': unread_notifications,
    }
    
    return render(request, 'dashboard/home.html', context)


# ============================================
# BUSINESS OWNER VIEWS - PHASE 4: Using TenantCustomer
# ============================================
@login_required
def manage_customers(request):
    """
    Business owner view to manage all customers
    Updated for Phase 4: Uses TenantCustomer with tenant scoping
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to identify business.')
        return redirect('/')
    
    # Check if user has permission (admin, owner, or staff)
    if request.user.role not in ['admin', 'owner', 'manager', 'staff']:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard:home')
    
    # Get all customers for this tenant
    
    customers = TenantCustomer.objects.filter(
        tenant=tenant,
        role='customer'  # Only show customers, not admin/staff
    ).order_by('-joined_at')
    
    # Search functionality
    search_query = request.GET.get('q', '')
    if search_query:
        customers = customers.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(customers, 25)
    page_number = request.GET.get('page')
    customers_page = paginator.get_page(page_number)
    
    context = {
        'tenant': tenant,
        'customers': customers_page,
        'search_query': search_query,
        'total_customers': customers.count(),
    }
    
    return render(request, 'dashboard/business_customers.html', context)


@login_required
def add_customer(request):
    """
    Business owner view to manually add a new customer
    Updated for Phase 4: Creates TenantCustomer
    """
    tenant = get_tenant_from_request(request)
    
    if not tenant:
        messages.error(request, 'Unable to identify business.')
        return redirect('/')
    
    # Check permissions
    if request.user.role not in ['admin', 'owner', 'staff']:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard:home')
    
    if request.method == 'POST':
        form = BusinessCustomerAddForm(request.POST, tenant=tenant)
        if form.is_valid():
            tenant_customer = form.save()
            messages.success(request, f'Customer {tenant_customer.get_full_name()} added successfully.')
            return redirect('dashboard:customer_detail', customer_id=tenant_customer.id)
    else:
        form = BusinessCustomerAddForm(tenant=tenant)
    
    context = {
        'tenant': tenant,
        'form': form,
    }
    
    return render(request, 'dashboard/business_customer_add.html', context)


@login_required
def customer_detail(request, customer_id):
    """
    Business owner view to see customer details
    Updated for Phase 4: Uses TenantCustomer
    """
    tenant = get_tenant_from_request(request)
    
    if not tenant:
        messages.error(request, 'Unable to identify business.')
        return redirect('/')
    
    # Get tenant customer
    tenant_customer = get_object_or_404(TenantCustomer, id=customer_id, tenant=tenant)
    
    # Get customer's transactions
    transactions = Transaction.objects.filter(
        tenant=tenant,
        tenant_customer=tenant_customer
    ).order_by('-transaction_date')[:20]
    
    # Calculate stats
    transaction_stats = Transaction.objects.filter(
        tenant=tenant,
        tenant_customer=tenant_customer
    ).aggregate(
        total_spent=Sum('total'),  # Changed from 'amount' to 'total'
        total_transactions=Count('id')  # Changed key name to match template
    )

    context = {
        'tenant': tenant,
        'customer': tenant_customer,
        'transactions': transactions,
        'total_spent': transaction_stats['total_spent'] or 0,  # Pass directly, not nested
        'total_transactions': transaction_stats['total_transactions'] or 0,  # Pass directly
    }
    
    return render(request, 'dashboard/business_customer_detail.html', context)


@login_required
def edit_customer(request, customer_id):
    """
    Business owner view to edit customer information
    Updated for Phase 4: Uses TenantCustomer
    """
    tenant = get_tenant_from_request(request)
    
    if not tenant:
        messages.error(request, 'Unable to identify business.')
        return redirect('/')
    
    # Check permissions
    if request.user.role not in ['admin', 'owner', 'staff']:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard:home')
    
    tenant_customer = get_object_or_404(TenantCustomer, id=customer_id, tenant=tenant)
    
    if request.method == 'POST':
        form = BusinessCustomerEditForm(
            request.POST,
            instance=tenant_customer,
          
        )
        if form.is_valid():
            form.save()
            messages.success(request, f'Customer {tenant_customer.get_full_name()} updated successfully.')
            return redirect('dashboard:customer_detail', customer_id=tenant_customer.id)
    else:
        form = BusinessCustomerEditForm(
            instance=tenant_customer,
           
        )
    
    context = {
        'tenant': tenant,
        'customer': tenant_customer,
        'form': form,
    }
    
    return render(request, 'dashboard/business_customer_edit.html', context)


@login_required
def delete_customer(request, customer_id):
    """
    Business owner view to delete/deactivate a customer
    Updated for Phase 4: Uses TenantCustomer
    """
    tenant = get_tenant_from_request(request)
    
    if not tenant:
        messages.error(request, 'Unable to identify business.')
        return redirect('/')
    
    # Check permissions
    if request.user.role not in ['admin', 'owner']:
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('dashboard:home')
    
    tenant_customer = get_object_or_404(TenantCustomer, id=customer_id, tenant=tenant)
    
    if request.method == 'POST':
        customer_name = tenant_customer.get_full_name()
        
        # Soft delete: deactivate instead of deleting
        tenant_customer.is_active = False
        tenant_customer.save()
        
        messages.success(request, f'Customer {customer_name} has been deactivated.')
        return redirect('dashboard:manage_customers')
    
    context = {
        'tenant': tenant,
        'customer': tenant_customer,
    }
    
    return render(request, 'dashboard/delete_customer_confirm.html', context)


@login_required
def edit_customer_notes(request, customer_id):
    """
    Quick edit for customer notes
    Updated for Phase 4: Uses TenantCustomer
    """
    tenant = get_tenant_from_request(request)
    
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    # Check permissions
    if request.user.role not in ['admin', 'owner', 'staff']:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    tenant_customer = get_object_or_404(TenantCustomer, id=customer_id, tenant=tenant)
    
    if request.method == 'POST':
        form = CustomerNotesForm(request.POST, instance=tenant_customer)
        if form.is_valid():
            form.save()
            return JsonResponse({
                'success': True,
                'message': 'Notes updated successfully',
                'notes': tenant_customer.notes
            })
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            }, status=400)
    
    form = CustomerNotesForm(instance=tenant_customer)
    return render(request, 'dashboard/edit_notes_modal.html', {
        'form': form,
        'customer': tenant_customer
    })


@login_required
def export_customers(request):
    """
    Export customers to CSV
    Updated for Phase 4: Uses TenantCustomer
    """
    import csv
    from django.http import HttpResponse
    
    tenant = get_tenant_from_request(request)
    
    if not tenant:
        messages.error(request, 'Unable to identify business.')
        return redirect('/')
    
    # Check permissions
    if request.user.role not in ['admin', 'owner', 'staff']:
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('dashboard:home')
    
    # Create the HttpResponse object with CSV header
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="customers_{tenant.subdomain}_{datetime.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'ID', 'Username', 'Email', 'First Name', 'Last Name', 'Phone',
        'Loyalty Points', 'Total Spent', 'Purchase Count', 'VIP Status',
        'Active', 'Joined Date', 'Last Purchase'
    ])
    
    customers = TenantCustomer.objects.filter(
        tenant=tenant,
        role='customer'
    ).order_by('-joined_at')
    
    for customer in customers:
        writer.writerow([
            str(customer.id),
            customer.username,
            customer.email,
            customer.first_name,
            customer.last_name,
            customer.phone or '',
            customer.loyalty_points,
            customer.total_spent or 0,
            customer.purchase_count or 0,
            'Yes' if customer.is_vip else 'No',
            'Yes' if customer.is_active else 'No',
            customer.joined_at.strftime('%Y-%m-%d') if customer.joined_at else '',
            customer.last_purchase_at.strftime('%Y-%m-%d') if customer.last_purchase_at else '',
        ])
    
    return response


# ============================================
# TRANSACTION VIEWS - PHASE 4: Using TenantCustomer
# ============================================
@login_required
def transaction_list(request):
    """
    List all transactions for the authenticated customer
    Updated for Phase 4: Uses TenantCustomer
    """
    if not TRANSACTIONS_ENABLED:
        messages.error(request, 'Transaction tracking is not enabled.')
        return redirect('/dashboard/')
    
    tenant = get_tenant_from_request(request)
    
    if not tenant:
        messages.error(request, 'Unable to identify business.')
        return redirect('/')
    
    # Get transactions for this customer in this tenant
    transactions = Transaction.objects.filter(
        tenant=tenant,
        tenant_customer=request.user
    ).order_by('-transaction_date')
    
    # Date filtering
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if date_from:
        transactions = transactions.filter(timestamp__gte=date_from)
    if date_to:
        transactions = transactions.filter(timestamp__lte=date_to)
    
    # Pagination
    paginator = Paginator(transactions, 20)
    page_number = request.GET.get('page')
    transactions_page = paginator.get_page(page_number)
    
    # Calculate totals
    total_spent = transactions.aggregate(total=Sum('amount'))['total'] or 0
    
    context = {
        'tenant': tenant,
        'transactions': transactions_page,
        'total_spent': total_spent,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'dashboard/transactions.html', context)


@login_required
def transaction_detail(request, transaction_id):
    """
    View details of a specific transaction
    Updated for Phase 4: Uses TenantCustomer
    """
    if not TRANSACTIONS_ENABLED:
        messages.error(request, 'Transaction tracking is not enabled.')
        return redirect('/dashboard/')
    
    tenant = get_tenant_from_request(request)
    
    if not tenant:
        messages.error(request, 'Unable to identify business.')
        return redirect('/')
    
    # Get transaction - ensure it belongs to this tenant and customer
    transaction = get_object_or_404(
        Transaction,
        transaction_id=transaction_id,
        tenant=tenant,
        tenant_customer=request.user
    )
    
    context = {
        'tenant': tenant,
        'transaction': transaction,
    }
    
    return render(request, 'dashboard/transaction_detail.html', context)


# ============================================
# PASSWORD RESET VIEWS (Tenant-aware)
# ============================================
class TenantPasswordResetView(PasswordResetView):
    """Custom password reset view that includes tenant context"""
    template_name = 'dashboard/password_reset.html'
    email_template_name = 'emails/password_reset_email.html'
    html_email_template_name = 'emails/password_reset_email.html'  # ADD THIS LINE
    success_url = reverse_lazy('dashboard:password_reset_done')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = get_tenant_from_request(self.request)
        return context


class TenantPasswordResetDoneView(PasswordResetDoneView):
    """Custom password reset done view with tenant context"""
    template_name = 'dashboard/password_reset_done.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = get_tenant_from_request(self.request)
        return context


class TenantPasswordResetConfirmView(PasswordResetConfirmView):
    """Custom password reset confirm view with tenant context"""
    template_name = 'dashboard/password_reset_confirm.html'
    success_url = reverse_lazy('dashboard:password_reset_complete')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = get_tenant_from_request(self.request)
        return context


class TenantPasswordResetCompleteView(PasswordResetCompleteView):
    """Custom password reset complete view with tenant context"""
    template_name = 'dashboard/password_reset_complete.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = get_tenant_from_request(self.request)
        return context
    
@require_http_methods(["GET"])
def get_tenant_info(request):
    """
    Temporary endpoint to get tenant UUIDs for POS sync.
    """
    secret = request.GET.get('secret', '')
    if secret != settings.INTEGRATION_SECRET:
        logger.warning(f"Unauthorized tenant info access attempt from {request.META.get('REMOTE_ADDR')}")
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        tenants = Tenant.objects.all().order_by('subdomain')
        
        tenant_list = []
        sql_updates = []
        
        for tenant in tenants:
            tenant_data = {
                'id': str(tenant.tenant_uuid),  # FIXED: use tenant_uuid
                'subdomain': tenant.subdomain,
                'name': tenant.name
            }
            tenant_list.append(tenant_data)
            
            sql = f"UPDATE Business SET externalTenantId = '{tenant.tenant_uuid}' WHERE businessName = '{tenant.name}';"  # FIXED
            sql_updates.append(sql)
        
        response_data = {
            'tenants': tenant_list,
            'count': len(tenant_list),
            'sql_updates': sql_updates,
            'database_type': 'production' if 'railway' in settings.DATABASES['default']['HOST'].lower() else 'local',
            'host': settings.DATABASES['default']['HOST']
        }
        
        logger.info(f"Tenant info retrieved successfully: {len(tenant_list)} tenants")
        return JsonResponse(response_data, json_dumps_params={'indent': 2})
        
    except Exception as e:
        logger.error(f"Error retrieving tenant info: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
    
@login_required
def toggle_theme(request):
    """
    Toggle theme preference (light/dark) and save to session.
    """
    if request.method == 'POST':
        import json
        data = json.loads(request.body)
        theme = data.get('theme', 'light')
        
        # Save theme preference to session
        request.session['theme'] = theme
        
        return JsonResponse({'success': True, 'theme': theme})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=400)


@login_required
def customer_notifications(request):
    """
    Customer notifications inbox - shows notifications received from business.
    """
    tenant = get_tenant_from_request(request)
    
    if not tenant:
        messages.error(request, 'Unable to identify business.')
        return redirect('/')
    
    customer = request.user
    
    # Get notifications for this customer
    notifications = NotificationRecipient.objects.filter(
        tenant_customer=customer
    ).select_related('notification').order_by('-created_at')
    
    # Filter by read status
    status_filter = request.GET.get('status', '')
    if status_filter == 'unread':
        notifications = notifications.filter(is_read=False)
    elif status_filter == 'read':
        notifications = notifications.filter(is_read=True)
    
    # Pagination
    paginator = Paginator(notifications, 20)
    page_number = request.GET.get('page')
    notifications_page = paginator.get_page(page_number)
    
    # Stats
    unread_count = NotificationRecipient.objects.filter(
        tenant_customer=customer,
        is_read=False
    ).count()
    
    total_count = NotificationRecipient.objects.filter(
        tenant_customer=customer
    ).count()
    
    context = {
        'tenant': tenant,
        'notifications': notifications_page,
        'unread_count': unread_count,
        'total_count': total_count,
        'status_filter': status_filter,
    }
    
    return render(request, 'dashboard/customer_notifications.html', context)


@login_required
def customer_notification_detail(request, notification_id):
    """
    View single notification and mark as read.
    """
    tenant = get_tenant_from_request(request)
    
    if not tenant:
        messages.error(request, 'Unable to identify business.')
        return redirect('/')
    
    customer = request.user
    
    # Get notification recipient
    notification_recipient = get_object_or_404(
        NotificationRecipient,
        id=notification_id,
        tenant_customer=customer
    )
    
    # Mark as read
    notification_recipient.mark_as_read()
    
    context = {
        'tenant': tenant,
        'notification_recipient': notification_recipient,
        'notification': notification_recipient.notification,
    }
    
    return render(request, 'dashboard/customer_notification_detail.html', context)


@login_required
def customer_messages(request):
    """
    Customer messages inbox - two-way conversations with business.
    Shows both messages sent by customer and received from business.
    """
    tenant = get_tenant_from_request(request)
    
    if not tenant:
        messages.error(request, 'Unable to identify business.')
        return redirect('/')
    
    customer = request.user
    
    # Get messages where customer is sender or receiver
    # Include messages sent to all staff (receiver=None)
    message_list = Message.objects.filter(
        tenant=tenant
    ).filter(
        Q(sender=customer) | Q(receiver=customer) | Q(receiver__isnull=True, message_type='business_to_customer')
    ).select_related('sender', 'receiver').order_by('-created_at')
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter == 'unread':
        message_list = message_list.filter(status__in=['sent', 'delivered'])
    elif status_filter == 'read':
        message_list = message_list.filter(status='read')
    
    # Pagination
    paginator = Paginator(message_list, 20)
    page_number = request.GET.get('page')
    messages_page = paginator.get_page(page_number)
    
    # Stats
    unread_count = Message.objects.filter(
        tenant=tenant,
        status__in=['sent', 'delivered']
    ).filter(
        Q(receiver=customer) | Q(receiver__isnull=True, message_type='business_to_customer')
    ).count()
    
    total_count = Message.objects.filter(
        tenant=tenant
    ).filter(
        Q(sender=customer) | Q(receiver=customer) | Q(receiver__isnull=True)
    ).count()
    
    context = {
        'tenant': tenant,
        'messages': messages_page,
        'unread_count': unread_count,
        'total_count': total_count,
        'status_filter': status_filter,
    }
    
    return render(request, 'dashboard/customer_messages.html', context)


@login_required
def customer_message_detail(request, message_id):
    """
    View single message thread and handle replies.
    """
    tenant = get_tenant_from_request(request)
    
    if not tenant:
        messages.error(request, 'Unable to identify business.')
        return redirect('/')
    
    customer = request.user
    
    # Get message
    message = get_object_or_404(
        Message,
        id=message_id,
        tenant=tenant
    )
    
    # Ensure customer has access to this message
    if message.sender != customer and message.receiver != customer and not (message.receiver is None and message.message_type == 'business_to_customer'):
        messages.error(request, 'You do not have access to this message.')
        return redirect('dashboard:customer_messages')
    
    # Mark as read if customer is receiver
    if message.receiver == customer or (message.receiver is None and message.message_type == 'business_to_customer'):
        message.mark_as_read()
    
    # Get conversation thread
    conversation = message.get_conversation_thread()
    
    # Handle reply submission
    if request.method == 'POST':
        reply_body = request.POST.get('reply_body', '').strip()
        
        if reply_body:
            # Create reply
            reply = Message.objects.create(
                tenant=tenant,
                sender=customer,
                receiver=None,  # Send to all staff
                message_type='customer_to_business',
                subject=f"Re: {message.subject}",
                body=reply_body,
                status='sent',
                sent_at=timezone.now(),
                parent_message=message if not message.parent_message else message.parent_message
            )
            
            messages.success(request, 'Reply sent successfully!')
            return redirect('dashboard:customer_message_detail', message_id=message.id)
        else:
            messages.error(request, 'Please enter a message.')
    
    context = {
        'tenant': tenant,
        'message': message,
        'conversation': conversation,
    }
    
    return render(request, 'dashboard/customer_message_detail.html', context)


@login_required
def compose_message_business(request):
    """
    Customer composes and sends message to business.
    """
    tenant = get_tenant_from_request(request)
    
    if not tenant:
        messages.error(request, 'Unable to identify business.')
        return redirect('/')
    
    customer = request.user
    
    if request.method == 'POST':
        subject = request.POST.get('subject', '').strip()
        body = request.POST.get('body', '').strip()
        priority = request.POST.get('priority', 'normal')
        
        if not subject or not body:
            messages.error(request, 'Please fill in all required fields.')
        else:
            # Create message
            message = Message.objects.create(
                tenant=tenant,
                sender=customer,
                receiver=None,  # Send to all staff
                message_type='customer_to_business',
                subject=subject,
                body=body,
                priority=priority,
                status='sent',
                sent_at=timezone.now()
            )
            
            messages.success(request, 'Message sent successfully!')
            return redirect('dashboard:customer_messages')
    
    context = {
        'tenant': tenant,
    }
    
    return render(request, 'dashboard/compose_message_business.html', context)

@csrf_exempt
@require_http_methods(["POST"])
def contact_form_view(request):
    """
    Handle contact form submissions and send email to admin@ayendecx.com
    """
    try:
        # Parse JSON data
        data = json.loads(request.body)
        
        # Extract form fields
        first_name = data.get('firstName', '')
        last_name = data.get('lastName', '')
        email = data.get('email', '')
        phone = data.get('phone', '')
        company = data.get('company', '')
        service = data.get('service', '')
        message = data.get('message', '')
        
        # Validate required fields
        if not all([first_name, last_name, email, service, message]):
            return JsonResponse({
                'success': False,
                'error': 'Missing required fields'
            }, status=400)
        
        # Prepare email content
        subject = f'New Contact Form Submission: {service}'
        
        email_body = f"""
New Contact Form Submission from Ayende CX Website

CONTACT DETAILS:
----------------
Name: {first_name} {last_name}
Email: {email}
Phone: {phone if phone else 'Not provided'}
Company: {company if company else 'Not provided'}
Service Interest: {service}

MESSAGE:
--------
{message}

SUBMISSION TIME: {data.get('timestamp', 'Not provided')}

---
This email was automatically generated from the contact form at ayendecx.com
        """
        
        # Send email
        try:
            send_mail(
                subject=subject,
                message=email_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=['admin@ayendecx.com'],
                fail_silently=False,
            )
            
            logger.info(f'Contact form email sent successfully from {email}')
            
            return JsonResponse({
                'success': True,
                'message': 'Thank you for your message! We will get back to you within 24 hours.'
            })
            
        except Exception as email_error:
            logger.error(f'Error sending contact form email: {str(email_error)}')
            return JsonResponse({
                'success': False,
                'error': 'Failed to send email. Please try again or contact us directly.'
            }, status=500)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
        
    except Exception as e:
        logger.error(f'Error processing contact form: {str(e)}')
        return JsonResponse({
            'success': False,
            'error': 'An error occurred processing your request'
        }, status=500)
# Add these imports at the top of dashboard/views/main.py:
# from customers.models import RentalContract, RentalContractItem
# from django.db.models import Sum, Count, Q

# Add these view functions to dashboard/views/main.py:

@login_required
def rental_list(request):
    """
    Display list of rental contracts for the business.
    Accessible to business owners and staff.
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, "Unable to determine your business.")
        return redirect('dashboard:home')
    
    # Get all rentals for this tenant
    rentals = RentalContract.objects.filter(tenant=tenant).select_related(
        'tenant_customer'
    ).prefetch_related('items').order_by('-created_at')
    
    # Apply filters
    status_filter = request.GET.get('status', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    if status_filter:
        rentals = rentals.filter(status=status_filter)
    
    if date_from:
        rentals = rentals.filter(start_date__gte=date_from)
    
    if date_to:
        rentals = rentals.filter(start_date__lte=date_to)
    
    # Calculate stats
    all_rentals = RentalContract.objects.filter(tenant=tenant)
    stats = {
        'active_count': all_rentals.filter(status='active').count(),
        'overdue_count': all_rentals.filter(status='overdue').count(),
        'returned_count': all_rentals.filter(status='returned').count(),
        'total_revenue': all_rentals.filter(
            status__in=['returned', 'closed']
        ).aggregate(total=Sum('total_paid'))['total'] or 0,
    }
    
    # Pagination
    paginator = Paginator(rentals, 20)
    page_number = request.GET.get('page')
    rentals = paginator.get_page(page_number)
    
    context = {
        'rentals': rentals,
        'stats': stats,
        'status_filter': status_filter,
        'tenant': tenant,
    }
    
    return render(request, 'dashboard/business_rentals.html', context)


@login_required
def rental_detail(request, rental_id):
    """
    Display detailed view of a single rental contract.
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, "Unable to determine your business.")
        return redirect('dashboard:home')
    
    rental = get_object_or_404(
        RentalContract.objects.select_related('tenant_customer').prefetch_related('items'),
        id=rental_id,
        tenant=tenant
    )
    
    context = {
        'rental': rental,
        'tenant': tenant,
    }
    
    return render(request, 'dashboard/business_rental_detail.html', context)
