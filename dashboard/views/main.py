from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Sum, Q, Count, Avg
from django.http import JsonResponse
from customers.models import Transaction, Customer, TenantCustomer
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
def check_customer_by_phone(request):
    """
    API endpoint to check if customer exists by phone number
    Updated for Phase 2/4: Uses TenantCustomer with tenant scoping
    """
    tenant = get_tenant_from_request(request)
    
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    
    phone = request.GET.get('phone')
    
    if not phone:
        return JsonResponse({'error': 'Phone number required'}, status=400)
    
    # Search for customer by phone in this tenant
    tenant_customer = TenantCustomer.objects.filter(
        tenant=tenant,
        phone=phone
    ).first()
    
    if tenant_customer:
        return JsonResponse({
            'exists': True,
            'customer': {
                'id': str(tenant_customer.id),
                'first_name': tenant_customer.first_name,
                'last_name': tenant_customer.last_name,
                'email': tenant_customer.email,
                'phone': tenant_customer.phone,
                'loyalty_points': tenant_customer.loyalty_points,
                'total_spent': float(tenant_customer.total_spent or 0),
                'visit_count': tenant_customer.visit_count or 0,
            }
        })
    
    return JsonResponse({'exists': False})


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
        return redirect('dashboard:home')
    
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
        return redirect('dashboard:home')
    
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
            if user.role in ['admin', 'owner', 'staff']:
                return redirect('/reports/')
            else:
                return redirect('dashboard:home')
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
def dashboard_home(request):
    """
    Customer dashboard home page
    Shows customer's transactions, loyalty points, and profile summary
    """
    tenant = get_tenant_from_request(request)
    
    if not tenant:
        messages.error(request, 'Unable to identify business.')
        return redirect('/')
    
    # Get TenantCustomer for current user
    tenant_customer = request.user
    
    # Get recent transactions
    recent_transactions = Transaction.objects.filter(
        tenant=tenant,
        tenant_customer=tenant_customer
    ).order_by('-timestamp')[:10]
    
    # Calculate stats
    total_transactions = Transaction.objects.filter(
        tenant=tenant,
        tenant_customer=tenant_customer
    ).count()
    
    context = {
        'tenant': tenant,
        'customer': tenant_customer,
        'recent_transactions': recent_transactions,
        'total_transactions': total_transactions,
        'loyalty_points': tenant_customer.loyalty_points,
        'total_spent': tenant_customer.total_spent,
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
    tenant = get_tenant_from_request(request)
    
    if not tenant:
        messages.error(request, 'Unable to identify business.')
        return redirect('/')
    
    # Check if user has permission (admin, owner, or staff)
    if request.user.role not in ['admin', 'owner', 'staff']:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard:home')
    
    # Get all customers for this tenant
    customers = TenantCustomer.objects.filter(tenant=tenant).order_by('-joined_at')
    
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
    
    return render(request, 'dashboard/manage_customers.html', context)


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
    
    return render(request, 'dashboard/add_customer.html', context)


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
    ).order_by('-timestamp')[:20]
    
    # Calculate stats
    transaction_stats = Transaction.objects.filter(
        tenant=tenant,
        tenant_customer=tenant_customer
    ).aggregate(
        total_spent=Sum('amount'),
        transaction_count=Count('id'),
        avg_transaction=Avg('amount')
    )
    
    context = {
        'tenant': tenant,
        'customer': tenant_customer,
        'transactions': transactions,
        'stats': transaction_stats,
    }
    
    return render(request, 'dashboard/customer_detail.html', context)


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
            customer=tenant_customer.customer
        )
        if form.is_valid():
            form.save()
            messages.success(request, f'Customer {tenant_customer.get_full_name()} updated successfully.')
            return redirect('dashboard:customer_detail', customer_id=tenant_customer.id)
    else:
        form = BusinessCustomerEditForm(
            instance=tenant_customer,
            customer=tenant_customer.customer
        )
    
    context = {
        'tenant': tenant,
        'customer': tenant_customer,
        'form': form,
    }
    
    return render(request, 'dashboard/edit_customer.html', context)


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
    
    customers = TenantCustomer.objects.filter(tenant=tenant).order_by('-joined_at')
    
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
        return redirect('dashboard:home')
    
    tenant = get_tenant_from_request(request)
    
    if not tenant:
        messages.error(request, 'Unable to identify business.')
        return redirect('/')
    
    # Get transactions for this customer in this tenant
    transactions = Transaction.objects.filter(
        tenant=tenant,
        tenant_customer=request.user
    ).order_by('-timestamp')
    
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
    
    return render(request, 'dashboard/transaction_list.html', context)


@login_required
def transaction_detail(request, transaction_id):
    """
    View details of a specific transaction
    Updated for Phase 4: Uses TenantCustomer
    """
    if not TRANSACTIONS_ENABLED:
        messages.error(request, 'Transaction tracking is not enabled.')
        return redirect('dashboard:home')
    
    tenant = get_tenant_from_request(request)
    
    if not tenant:
        messages.error(request, 'Unable to identify business.')
        return redirect('/')
    
    # Get transaction - ensure it belongs to this tenant and customer
    transaction = get_object_or_404(
        Transaction,
        id=transaction_id,
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