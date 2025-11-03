from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Sum, Q, Count, Avg
from django.http import JsonResponse
from customers.models import Transaction, Customer, TenantCustomer
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

# Import forms used in views
from dashboard.forms import (
    CustomerRegistrationForm,
    CustomerLoginForm,
    BusinessCustomerAddForm,
    BusinessCustomerEditForm,
    CustomerNotesForm,
)

# ============================================
# INTEGRATION: REST Framework imports
# ============================================
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from dashboard.authentication import IntegrationJWTAuthentication
# dashboard/views.py (or customers/views.py)
# Add this view function to handle phone number lookups

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from customers.models import Customer
import json
# dashboard/views.py (or customers/views.py)
# Add this view function to handle phone number lookups

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from customers.models import Customer
import json

@require_http_methods(["GET"])
def check_customer_by_phone(request):
    """
    Check if a customer exists by phone number.
    Used by POS system to check for duplicates before creating customers.
    
    Query params:
        phone: Phone number to search for
        
    Returns:
        JSON with customer data if found, or {"exists": false} if not found
    """
    try:
        phone = request.GET.get('phone')
        
        if not phone:
            return JsonResponse({
                'exists': False,
                'error': 'Phone number is required'
            }, status=400)
        
        # Normalize phone number (remove non-digits)
        normalized_phone = ''.join(filter(str.isdigit, phone))
        
        if not normalized_phone:
            return JsonResponse({
                'exists': False,
                'error': 'Invalid phone number'
            }, status=400)
        
        # Search for customer by phone
        # Use contains to match various phone formats
        customer = Customer.objects.filter(
            phone__contains=normalized_phone
        ).first()
        
        if customer:
            # Customer found - return data
            return JsonResponse({
                'exists': True,
                'customer': {
                    'id': str(customer.id),
                    'first_name': customer.first_name,
                    'last_name': customer.last_name,
                    'email': customer.email or '',
                    'phone': customer.phone or '',
                    'date_of_birth': customer.date_of_birth.isoformat() if customer.date_of_birth else None,
                    'address': customer.address or '',
                    'city': customer.city or '',
                    'state': customer.state or '',
                    'zip_code': customer.zip_code or '',
                    'loyalty_points': customer.loyalty_points or 0,
                    'loyalty_tier': customer.loyalty_tier or 'BRONZE',
                    'total_spent': float(customer.total_spent or 0),
                    'visit_count': customer.visit_count or 0,
                    'marketing_opt_in': customer.marketing_opt_in or False,
                    'is_active': customer.is_active,
                    'created_at': customer.created_at.isoformat() if customer.created_at else None,
                    'updated_at': customer.updated_at.isoformat() if customer.updated_at else None,
                }
            })
        else:
            # Customer not found
            return JsonResponse({
                'exists': False
            })
            
    except Exception as e:
        return JsonResponse({
            'exists': False,
            'error': str(e)
        }, status=500)

@require_http_methods(["GET"])
def check_customer_by_phone(request):
    """
    Check if a customer exists by phone number.
    Used by POS system to check for duplicates before creating customers.
    
    Query params:
        phone: Phone number to search for
        
    Returns:
        JSON with customer data if found, or {"exists": false} if not found
    """
    try:
        phone = request.GET.get('phone')
        
        if not phone:
            return JsonResponse({
                'exists': False,
                'error': 'Phone number is required'
            }, status=400)
        
        # Normalize phone number (remove non-digits)
        normalized_phone = ''.join(filter(str.isdigit, phone))
        
        if not normalized_phone:
            return JsonResponse({
                'exists': False,
                'error': 'Invalid phone number'
            }, status=400)
        
        # Search for customer by phone
        # Use contains to match various phone formats
        customer = Customer.objects.filter(
            phone__contains=normalized_phone
        ).first()
        
        if customer:
            # Customer found - return data
            return JsonResponse({
                'exists': True,
                'customer': {
                    'id': str(customer.id),
                    'first_name': customer.first_name,
                    'last_name': customer.last_name,
                    'email': customer.email or '',
                    'phone': customer.phone or '',
                    'date_of_birth': customer.date_of_birth.isoformat() if customer.date_of_birth else None,
                    'address': customer.address or '',
                    'city': customer.city or '',
                    'state': customer.state or '',
                    'zip_code': customer.zip_code or '',
                    'loyalty_points': customer.loyalty_points or 0,
                    'loyalty_tier': customer.loyalty_tier or 'BRONZE',
                    'total_spent': float(customer.total_spent or 0),
                    'visit_count': customer.visit_count or 0,
                    'marketing_opt_in': customer.marketing_opt_in or False,
                    'is_active': customer.is_active,
                    'created_at': customer.created_at.isoformat() if customer.created_at else None,
                    'updated_at': customer.updated_at.isoformat() if customer.updated_at else None,
                }
            })
        else:
            # Customer not found
            return JsonResponse({
                'exists': False
            })
            
    except Exception as e:
        return JsonResponse({
            'exists': False,
            'error': str(e)
        }, status=500)

def landing_page(request):
    """
    Public landing page view - accessible to everyone
    Shows tenant-specific branding if accessed via tenant subdomain
    """
    tenant = getattr(request, 'tenant', None)
    
    # Debug prints
    print(f"=== LANDING PAGE DEBUG ===")
    print(f"Host: {request.get_host()}")
    print(f"Tenant: {tenant}")
    if tenant:
        print(f"Tenant name: {tenant.name}")
        print(f"Tenant subdomain: {tenant.subdomain}")
    print(f"========================")
    
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
    
# Check if Transaction model exists, if not, skip transaction views
try:
    from customers.models import Transaction
    TRANSACTIONS_ENABLED = True
except ImportError:
    TRANSACTIONS_ENABLED = False


def customer_register(request):
    """
    Customer self-registration view with email verification.
    Customer must verify email before they can login.
    """
   # Redirect if already logged in
    if request.user.is_authenticated:
        # Role-based redirect for already authenticated users
        if hasattr(request.user, 'role') and request.user.role in ['ADMIN', 'OWNER', 'STAFF']:
            return redirect('/reports/')  # Business dashboard
        return redirect('dashboard:home')  # Customer portal
    
    # Get tenant from middleware
    tenant = getattr(request, 'tenant', None)
    
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
        form = CustomerRegistrationForm(request.POST, tenant=tenant)
        if form.is_valid():
            customer = form.save()
            
            # Send verification email (DO NOT auto-login)
            send_verification_email(customer, tenant, request)
            
            messages.success(
                request,
                f'Welcome {customer.first_name}! Please check your email to verify your account before logging in.'
            )
            messages.info(
                request,
                f'A verification email has been sent to {customer.email}. Please check your inbox.'
            )
            return redirect('dashboard:login')
    else:
        form = CustomerRegistrationForm(tenant=tenant)
    
    context = {
        'form': form,
        'tenant': tenant
    }
    return render(request, 'dashboard/register.html', context)

def send_verification_email(customer, tenant, request):
    """
    Send verification email to customer
    """
    # Generate verification token
    token = customer.generate_verification_token()
    
    # Build verification URL
    verification_url = request.build_absolute_uri(
        f'/verify-email/{token}/'
    )
    
    # Email context
    context = {
        'customer': customer,
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
        recipient_list=[customer.email],
        html_message=html_message,
        fail_silently=False,
    )


def verify_email(request, token):
    """
    Verify email address using token
    """
    # Find customer with this token
    try:
        customer = Customer.objects.get(email_verification_token=token)
    except Customer.DoesNotExist:
        messages.error(request, 'Invalid verification link. Please try again or request a new verification email.')
        return redirect('dashboard:login')
    
    # Check if token is expired
    if not customer.is_verification_token_valid():
        messages.error(
            request,
            'Verification link has expired. We\'ve sent you a new verification email.'
        )
        # Resend verification email
        tenant = getattr(request, 'tenant', None)
        if tenant:
            send_verification_email(customer, tenant, request)
        return redirect('dashboard:login')
    
    # Verify the email
    customer.verify_email()
    
    messages.success(
        request,
        'Email verified successfully! You can now login to your account.'
    )
    return redirect('dashboard:login')


def resend_verification_email(request):
    """
    Resend verification email
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to identify business.')
        return redirect('/')
    
    if request.method == 'POST':
        email = request.POST.get('email')
        
        try:
            # Find customer by email and tenant
            from customers.models import TenantCustomer
            tenant_customer = TenantCustomer.objects.get(
                customer__email=email,
                tenant=tenant
            )
            customer = tenant_customer.customer
            
            # Check if already verified
            if customer.email_verified:
                messages.info(request, 'Your email is already verified. You can login now.')
                return redirect('dashboard:login')
            
            # Send verification email
            send_verification_email(customer, tenant, request)
            
            messages.success(
                request,
                f'Verification email sent to {email}. Please check your inbox.'
            )
            return redirect('dashboard:login')
            
        except TenantCustomer.DoesNotExist:
            # Don't reveal if email exists or not (security)
            messages.success(
                request,
                f'If an account exists with {email}, a verification email has been sent.'
            )
            return redirect('dashboard:login')
    
    context = {
        'tenant': tenant
    }
    return render(request, 'dashboard/resend_verification.html', context)


def customer_login_view(request):
    """
    Customer login view - handles authentication and tenant verification
    """
    # Redirect if already logged in
    if request.user.is_authenticated:
        return redirect('dashboard:home')
    
    # Get tenant from middleware
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to identify business. Please check the URL.')
        return redirect('/')
    
    if request.method == 'POST':
        form = CustomerLoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            
            # Authenticate user
            user = authenticate(request, username=email, password=password)
            
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
                        'form': form,
                        'tenant': tenant
                    })
                
                # Check if user belongs to this tenant
                try:
                    TenantCustomer.objects.get(customer=user, tenant=tenant)
                    login(request, user)
                    
                    messages.success(request, f'Welcome back, {user.first_name}!')
                    
                    # ============================================
                    # ROLE-BASED REDIRECT LOGIC
                    # ============================================
                    # Check if there's a 'next' parameter
                    next_url = request.GET.get('next')
                    
                    if next_url:
                        # If there's a next URL, use it
                        return redirect(next_url)
                    else:
                        # Role-based redirect
                        if hasattr(user, 'role'):
                            if user.role in ['ADMIN', 'OWNER', 'STAFF']:
                                # Business users → Reports dashboard
                                return redirect('/reports/')
                            else:
                                # Customers → Customer portal
                                return redirect('dashboard:home')
                        else:
                            # No role attribute → assume customer
                            return redirect('dashboard:home')
                    
                except TenantCustomer.DoesNotExist:
                    messages.error(
                        request,
                        'This account does not have access to this business.'
                    )
            else:
                messages.error(request, 'Invalid email or password.')
    else:
        form = CustomerLoginForm()
    
    context = {
        'form': form,
        'tenant': tenant
    }
    return render(request, 'dashboard/login.html', context)


def customer_logout_view(request):
    """
    Customer logout view
    """
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('dashboard:login')


@login_required(login_url='dashboard:login')
def dashboard_home(request):
    """
    Main dashboard view showing customer's transaction history,
    loyalty points, and recent activity
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to load dashboard. Please check your URL.')
        return redirect('/')
    
    # Get the tenant-specific customer record
    try:
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
    except TenantCustomer.DoesNotExist:
        messages.error(request, "Customer record not found for this business.")
        logout(request)
        return redirect('dashboard:login')
    
    # Get recent transactions
    recent_transactions = Transaction.objects.filter(
        tenant=tenant,
        customer=request.user
    ).order_by('-transaction_date')[:5]
    
    # Calculate statistics
    total_transactions = Transaction.objects.filter(
        tenant=tenant,
        customer=request.user
    ).count()
    
    total_spent = Transaction.objects.filter(
        tenant=tenant,
        customer=request.user
    ).aggregate(total=Sum('total'))['total'] or 0
    
    total_points_earned = Transaction.objects.filter(
        tenant=tenant,
        customer=request.user
    ).aggregate(points=Sum('points_earned'))['points'] or 0
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'recent_transactions': recent_transactions,
        'total_transactions': total_transactions,
        'total_spent': total_spent,
        'total_points_earned': total_points_earned,
    }
    
    return render(request, 'dashboard/home.html', context)


# ============================================================================
# BUSINESS OWNER VIEWS (Customer Management)
# ============================================================================

@login_required(login_url='dashboard:login')
def manage_customers(request):
    """
    Business owner view to manage customers
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to load customers.')
        return redirect('dashboard:home')
    
    # Verify user has permission (is_staff_member in TenantCustomer)
    try:
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
        
        if not tenant_customer.is_staff_member:
            messages.error(request, 'You do not have permission to manage customers.')
            return redirect('dashboard:home')
            
    except TenantCustomer.DoesNotExist:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:home')
    
    # Get all customers for this tenant
    customers_qs = TenantCustomer.objects.filter(
        tenant=tenant
    ).select_related('customer').order_by('-customer__date_joined')
    
    # Apply search filter
    search = request.GET.get('search', '')
    if search:
        customers_qs = customers_qs.filter(
            Q(customer__first_name__icontains=search) |
            Q(customer__last_name__icontains=search) |
            Q(customer__email__icontains=search) |
            Q(customer__phone__icontains=search)
        )
    
    # Paginate results
    paginator = Paginator(customers_qs, 20)
    page_number = request.GET.get('page')
    customers_page = paginator.get_page(page_number)
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'customers': customers_page,
        'search': search,
        'is_business_view': True,
    }
    
    return render(request, 'dashboard/business_customers.html', context)


@login_required(login_url='dashboard:login')
def add_customer(request):
    """
    Business owner view to manually add a customer
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to add customer.')
        return redirect('dashboard:home')
    
    # Verify permissions
    try:
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
        
        if not tenant_customer.is_staff_member:
            messages.error(request, 'You do not have permission to add customers.')
            return redirect('dashboard:home')
            
    except TenantCustomer.DoesNotExist:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:home')
    
    if request.method == 'POST':
        form = BusinessCustomerAddForm(request.POST, tenant=tenant)
        if form.is_valid():
            new_customer = form.save()
            
            messages.success(
                request,
                f'Customer {new_customer.customer.get_full_name()} has been added successfully.'
            )
            return redirect('dashboard:manage_customers')
    else:
        form = BusinessCustomerAddForm(tenant=tenant)
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'form': form,
        'is_business_view': True,
    }
    
    return render(request, 'dashboard/add_customer.html', context)


@login_required(login_url='dashboard:login')
def customer_detail(request, customer_id):
    """
    View detailed information about a specific customer
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to load customer details.')
        return redirect('dashboard:home')
    
    # Verify permissions
    try:
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
        
        if not tenant_customer.is_staff_member:
            messages.error(request, 'You do not have permission to view customer details.')
            return redirect('dashboard:home')
            
    except TenantCustomer.DoesNotExist:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:home')
    
    # Get the customer
    customer_rel = get_object_or_404(
        TenantCustomer,
        id=customer_id,
        tenant=tenant
    )
    
    # Get customer's transactions
    transactions = Transaction.objects.filter(
        tenant=tenant,
        customer=customer_rel.customer
    ).order_by('-transaction_date')[:10]
    
    # Calculate statistics
    total_spent = Transaction.objects.filter(
        tenant=tenant,
        customer=customer_rel.customer
    ).aggregate(total=Sum('total'))['total'] or 0
    
    total_transactions = Transaction.objects.filter(
        tenant=tenant,
        customer=customer_rel.customer
    ).count()
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'customer_rel': customer_rel,
        'transactions': transactions,
        'total_spent': total_spent,
        'total_transactions': total_transactions,
        'is_business_view': True,
    }
    
    return render(request, 'dashboard/customer_detail.html', context)


@login_required(login_url='dashboard:login')
def edit_customer(request, customer_id):
    """
    Business owner view to edit customer information
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to edit customer.')
        return redirect('dashboard:home')
    
    # Verify permissions
    try:
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
        
        if not tenant_customer.is_staff_member:
            messages.error(request, 'You do not have permission to edit customers.')
            return redirect('dashboard:home')
            
    except TenantCustomer.DoesNotExist:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:home')
    
    # Get the customer
    customer_rel = get_object_or_404(
        TenantCustomer,
        id=customer_id,
        tenant=tenant
    )
    
    if request.method == 'POST':
        form = BusinessCustomerEditForm(
            request.POST, 
            instance=customer_rel.customer,
            tenant_customer=customer_rel
        )
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f'Customer {customer_rel.customer.get_full_name()} has been updated successfully.'
            )
            return redirect('dashboard:customer_detail', customer_id=customer_id)
    else:
        form = BusinessCustomerEditForm(
            instance=customer_rel.customer,
            tenant_customer=customer_rel
        )
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'form': form,
        'customer_rel': customer_rel,
        'is_business_view': True,
    }
    
    return render(request, 'dashboard/edit_customer.html', context)


@login_required(login_url='dashboard:login')
def delete_customer(request, customer_id):
    """
    Business owner view to remove a customer from their system
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to delete customer.')
        return redirect('dashboard:home')
    
    # Verify permissions
    try:
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
        
        if not tenant_customer.is_staff_member:
            messages.error(request, 'You do not have permission to delete customers.')
            return redirect('dashboard:home')
            
    except TenantCustomer.DoesNotExist:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:home')
    
    # Get the customer
    customer_rel = get_object_or_404(
        TenantCustomer,
        id=customer_id,
        tenant=tenant
    )
    
    if request.method == 'POST':
        customer_name = customer_rel.customer.get_full_name()
        
        # Only delete the TenantCustomer relationship, not the Customer
        # This preserves the customer if they belong to other tenants
        customer_rel.delete()
        
        messages.success(
            request,
            f'Customer {customer_name} has been removed from your system.'
        )
        return redirect('dashboard:manage_customers')
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'is_business_view': True,
        'customer_rel': customer_rel,
    }
    
    return render(request, 'dashboard/business_customer_delete.html', context)


@login_required(login_url='dashboard:login')
def edit_customer_notes(request, customer_id):
    """
    Quick edit view for customer notes (AJAX).
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        return JsonResponse({'success': False, 'error': 'Invalid tenant'})
    
    # Verify permissions
    try:
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
        
        if not tenant_customer.is_staff_member:
            return JsonResponse({'success': False, 'error': 'Permission denied'})
            
    except TenantCustomer.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Access denied'})
    
    # Get the customer
    customer_rel = get_object_or_404(
        TenantCustomer,
        id=customer_id,
        tenant=tenant
    )
    
    if request.method == 'POST':
        form = CustomerNotesForm(request.POST, instance=customer_rel)
        if form.is_valid():
            form.save()
            return JsonResponse({
                'success': True,
                'notes': customer_rel.notes
            })
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            })
    
    # GET request - return current notes
    return JsonResponse({
        'success': True,
        'notes': customer_rel.notes
    })


# ============================================================================
# TRANSACTION VIEWS
# ============================================================================

@login_required(login_url='dashboard:login')
def transaction_list(request):
    """
    Display list of all transactions for the logged-in customer
    with filtering and pagination
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to load transactions.')
        return redirect('dashboard:home')
    
    # Get the tenant-specific customer record
    try:
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
    except TenantCustomer.DoesNotExist:
        messages.error(request, "Customer record not found for this business.")
        return redirect('dashboard:home')
    
    # Get all transactions for this customer
    transactions = Transaction.objects.filter(
        tenant=tenant,
        customer=request.user
    ).order_by('-transaction_date')
    
    # Apply filters
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            transactions = transactions.filter(transaction_date__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            transactions = transactions.filter(transaction_date__lte=date_to_obj)
        except ValueError:
            pass
    
    # Calculate summary statistics
    total_spent = transactions.aggregate(total=Sum('total'))['total'] or 0
    total_transactions = transactions.count()
    total_points_earned = transactions.aggregate(points=Sum('points_earned'))['points'] or 0
    
    # Paginate results
    paginator = Paginator(transactions, 20)
    page_number = request.GET.get('page')
    transactions_page = paginator.get_page(page_number)
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'transactions': transactions_page,
        'total_spent': total_spent,
        'total_transactions': total_transactions,
        'total_points_earned': total_points_earned,
    }
    
    return render(request, 'dashboard/transactions.html', context)


@login_required(login_url='dashboard:login')
def transaction_detail(request, transaction_id):
    """
    Display detailed information about a specific transaction
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to load transaction.')
        return redirect('dashboard:home')
    
    # Get the transaction - ensure it belongs to this customer and tenant
    transaction = get_object_or_404(
        Transaction,
        transaction_id=transaction_id,
        tenant=tenant,
        customer=request.user
    )
    
    # Get the tenant-specific customer record
    try:
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
    except TenantCustomer.DoesNotExist:
        tenant_customer = None
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'transaction': transaction,
    }
    
    return render(request, 'dashboard/transaction_detail.html', context)


# ============================================================================
# PASSWORD RESET VIEWS
# ============================================================================

class TenantPasswordResetView(PasswordResetView):
    """
    Custom password reset view that includes tenant context
    """
    template_name = 'dashboard/password_reset.html'
    email_template_name = 'dashboard/password_reset_email.txt'
    html_email_template_name = 'dashboard/password_reset_email.html'
    subject_template_name = 'dashboard/password_reset_subject.txt'
    success_url = reverse_lazy('dashboard:password_reset_done')
    form_class = PasswordResetForm
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = getattr(self.request, 'tenant', None)
        return context


class TenantPasswordResetDoneView(PasswordResetDoneView):
    """
    View shown after password reset email is sent
    """
    template_name = 'dashboard/password_reset_done.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = getattr(self.request, 'tenant', None)
        return context


class TenantPasswordResetConfirmView(PasswordResetConfirmView):
    """
    View for confirming password reset with token
    """
    template_name = 'dashboard/password_reset_confirm.html'
    success_url = reverse_lazy('dashboard:password_reset_complete')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = getattr(self.request, 'tenant', None)
        return context


class TenantPasswordResetCompleteView(PasswordResetCompleteView):
    """
    View shown after password reset is complete
    """
    template_name = 'dashboard/password_reset_complete.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = getattr(self.request, 'tenant', None)
        return context


# ============================================================================
# INTEGRATION VIEWS - POS SYNC ENDPOINTS
# ============================================================================

class SyncHealthView(APIView):
    """
    Health check endpoint for integration
    Returns status of CRM system
    """
    authentication_classes = [IntegrationJWTAuthentication]
    
    def get(self, request):
        """Check if CRM is healthy and ready to receive data"""
        return Response({
            'status': 'healthy',
            'message': 'CRM system is ready to receive sync requests',
            'version': '1.0.0',
        })
        
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from customers.models import Customer

@require_http_methods(["GET"])
def check_customer_by_phone(request):
    """
    Check if a customer exists by phone number.
    Used by POS system to check for duplicates before creating customers.
    """
    try:
        phone = request.GET.get('phone')
        
        if not phone:
            return JsonResponse({
                'exists': False,
                'error': 'Phone number is required'
            }, status=400)
        
        # Normalize phone number (remove non-digits)
        normalized_phone = ''.join(filter(str.isdigit, phone))
        
        if not normalized_phone:
            return JsonResponse({
                'exists': False,
                'error': 'Invalid phone number'
            }, status=400)
        
        # Search for customer by phone
        customer = Customer.objects.filter(
            phone__contains=normalized_phone
        ).first()
        
        if customer:
            # Customer found - return data
            return JsonResponse({
                'exists': True,
                'customer': {
                    'id': str(customer.id),
                    'first_name': customer.first_name,
                    'last_name': customer.last_name,
                    'email': customer.email or '',
                    'phone': customer.phone or '',
                    'date_of_birth': customer.date_of_birth.isoformat() if customer.date_of_birth else None,
                    'address': customer.address or '',
                    'city': customer.city or '',
                    'state': customer.state or '',
                    'zip_code': customer.zip_code or '',
                    'loyalty_points': customer.loyalty_points or 0,
                    'loyalty_tier': customer.loyalty_tier or 'BRONZE',
                    'total_spent': float(customer.total_spent or 0),
                    'visit_count': customer.visit_count or 0,
                    'marketing_opt_in': customer.marketing_opt_in or False,
                    'is_active': customer.is_active,
                    'created_at': customer.created_at.isoformat() if customer.created_at else None,
                    'updated_at': customer.updated_at.isoformat() if customer.updated_at else None,
                }
            })
        else:
            # Customer not found
            return JsonResponse({
                'exists': False
            })
            
    except Exception as e:
        return JsonResponse({
            'exists': False,
            'error': str(e)
        }, status=500)
