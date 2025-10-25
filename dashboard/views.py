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
        return redirect('dashboard:home')
    
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
            messages.error(request, 'No account found with that email address.')
    
    context = {
        'tenant': tenant,
    }
    return render(request, 'dashboard/resend_verification.html', context)


def customer_login_view(request):
    """
    Customer login view with tenant-aware authentication and email verification check.
    """
    # Redirect if already logged in
    if request.user.is_authenticated:
        return redirect('dashboard:home')
    
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to identify business. Please check the URL.')
        return redirect('/')
    
    if request.method == 'POST':
        form = CustomerLoginForm(request.POST, request=request)
        if form.is_valid():
            email = form.cleaned_data.get('email')
            password = form.cleaned_data.get('password')
            
            # Authenticate
            user = authenticate(request, username=email, password=password)
            
            if user is not None:
                # Verify user belongs to this tenant
                try:
                    tenant_customer = TenantCustomer.objects.get(
                        customer=user,
                        tenant=tenant
                    )
                    
                    # CHECK EMAIL VERIFICATION (NEW)
                    if not user.email_verified:
                        messages.error(
                            request,
                            'Please verify your email address before logging in. Check your inbox for the verification link.'
                        )
                        # Add resend link to message
                        messages.warning(
                            request,
                            mark_safe(
                                'Didn\'t receive the email? '
                                '<a href="/resend-verification/" class="alert-link">Resend verification email</a>'
                            )
                        )
                        return render(request, 'dashboard/login.html', {
                            'form': form,
                            'tenant': tenant,
                            'show_resend_link': True,
                            'user_email': email,
                        })
                    
                    # Email is verified, proceed with login
                    login(request, user, backend='tenants.backends.TenantAwareAuthBackend')
                    messages.success(request, f'Welcome back, {user.first_name}!')
                    
                    # Redirect to next parameter or dashboard
                    next_url = request.GET.get('next', 'dashboard:home')
                    return redirect(next_url)
                    
                except TenantCustomer.DoesNotExist:
                    messages.error(
                        request,
                        'You do not have access to this business. Please check your credentials.'
                    )
            else:
                messages.error(request, 'Invalid email or password.')
    else:
        form = CustomerLoginForm(request=request)
    
    context = {
        'form': form,
        'tenant': tenant
    }
    return render(request, 'dashboard/login.html', context)


@login_required(login_url='dashboard:login')
def customer_logout_view(request):
    """
    Customer logout view.
    """
    first_name = request.user.first_name
    logout(request)
    messages.success(request, f'Goodbye {first_name}! You have been logged out successfully.')
    return redirect('dashboard:login')


@login_required(login_url='dashboard:login')
def dashboard_home(request):
    """
    Dashboard home page - routes to different dashboards based on role.
    Business owners/staff see business dashboard.
    Regular customers see customer dashboard.
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to load dashboard.')
        return redirect('dashboard:login')
    
    # Get customer-tenant relationship
    try:
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
    except TenantCustomer.DoesNotExist:
        messages.error(request, 'You do not have access to this dashboard.')
        logout(request)
        return redirect('dashboard:login')
    
    # Route based on role - business staff get separate interface
    if tenant_customer.is_staff_member:
        return business_dashboard(request, tenant, tenant_customer)
    else:
        return customer_dashboard(request, tenant, tenant_customer)


def customer_dashboard(request, tenant, tenant_customer):
    """
    Regular customer dashboard view.
    Shows personalized stats and tenant information.
    """
    # Get recent transactions if available
    recent_transactions = []
    if TRANSACTIONS_ENABLED:
        recent_transactions = Transaction.objects.filter(
            tenant=tenant,
            customer=request.user,
            status='completed'
        ).order_by('-transaction_date')[:5]
    
    # Calculate total spent
    total_spent = 0
    if TRANSACTIONS_ENABLED:
        total_spent = sum(
            t.total for t in Transaction.objects.filter(
                tenant=tenant,
                customer=request.user,
                status='completed'
            )
        )
    from notifications.models import NotificationRecipient
    unread_count = NotificationRecipient.objects.filter(
        tenant_customer=tenant_customer,
        is_read=False
    ).count()
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'loyalty_points': tenant_customer.loyalty_points,
        'total_purchases': tenant_customer.total_purchases,
        'total_spent': total_spent,
        'recent_transactions': recent_transactions,
    }
    return render(request, 'dashboard/home.html', context)


def business_dashboard(request, tenant, tenant_customer):
    """
    Business owner/staff dashboard view.
    Shows business statistics, customer overview, and management tools.
    
    CRITICAL FIX: Properly attaches tenant_customer to each transaction
    """
    from django.utils import timezone
    
    # Get all customers for this tenant
    all_customers = TenantCustomer.objects.filter(
        tenant=tenant,
        role='customer',
        is_active=True
    ).select_related('customer')
    
    # Customer statistics
    total_customers = all_customers.count()
    
    # Get customers who joined in last 30 days
    thirty_days_ago = timezone.now() - timedelta(days=30)
    new_customers = all_customers.filter(joined_at__gte=thirty_days_ago).count()
    
    # Transaction statistics (if enabled)
    total_revenue = 0
    total_transactions = 0
    recent_transactions = []
    avg_transaction_value = 0
    
    if TRANSACTIONS_ENABLED:
        completed_transactions = Transaction.objects.filter(
            tenant=tenant
        )
        
        # Get aggregated stats
        stats = completed_transactions.aggregate(
            total_revenue=Sum('total'),
            total_count=Count('id'),
            avg_value=Avg('total')
        )
        
        total_revenue = stats['total_revenue'] or 0
        total_transactions = stats['total_count'] or 0
        avg_transaction_value = stats['avg_value'] or 0
        
        # Get recent transactions with customer info - CRITICAL FIX
        recent_trans_qs = completed_transactions.select_related('customer').order_by('-transaction_date')[:10]
        
        # Attach tenant_customer to each transaction
        for transaction in recent_trans_qs:
            try:
                transaction.tenant_customer = TenantCustomer.objects.get(
                    tenant=tenant,
                    customer=transaction.customer
                )
            except TenantCustomer.DoesNotExist:
                transaction.tenant_customer = None
        
        recent_transactions = list(recent_trans_qs)
    
    # Top customers by spending
    top_customers = all_customers.order_by('-total_spent')[:5]
    
    # Pagination for customer list
    customers_page = request.GET.get('page', 1)
    paginator = Paginator(all_customers, 20)  # 20 customers per page
    customers = paginator.get_page(customers_page)
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'is_business_view': True,
        
        # Customer stats
        'total_customers': total_customers,
        'new_customers': new_customers,
        'top_customers': top_customers,
        'customers': customers,
        
        # Transaction stats
        'total_revenue': total_revenue,
        'total_transactions': total_transactions,
        'avg_transaction_value': avg_transaction_value,
        'recent_transactions': recent_transactions,
    }
    
    return render(request, 'dashboard/business_home.html', context)


@login_required(login_url='dashboard:login')
def manage_customers(request):
    """
    Business owner view to manage all customers.
    Provides search, filter, and pagination.
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to load customer list.')
        return redirect('dashboard:home')
    
    # Verify permissions
    try:
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
        
        if not tenant_customer.is_staff_member:
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('dashboard:home')
            
    except TenantCustomer.DoesNotExist:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:login')
    
    # Get all customers
    customers = TenantCustomer.objects.filter(
        tenant=tenant,
        role='customer'
    ).select_related('customer').order_by('-joined_at')
    
    # Search functionality
    search_query = request.GET.get('search', '').strip()
    if search_query:
        customers = customers.filter(
            Q(customer__first_name__icontains=search_query) |
            Q(customer__last_name__icontains=search_query) |
            Q(customer__email__icontains=search_query) |
            Q(customer__phone__icontains=search_query)
        )
    
    # Filter by VIP status
    vip_filter = request.GET.get('vip', '')
    if vip_filter == 'yes':
        customers = customers.filter(is_vip=True)
    elif vip_filter == 'no':
        customers = customers.filter(is_vip=False)
    
    # Filter by active status
    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        customers = customers.filter(is_active=True)
    elif status_filter == 'inactive':
        customers = customers.filter(is_active=False)
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(customers, 25)
    customers_page = paginator.get_page(page)
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'is_business_view': True,
        'customers': customers_page,
        'search_query': search_query,
        'vip_filter': vip_filter,
        'status_filter': status_filter,
        'total_customers': customers.count(),
    }
    
    return render(request, 'dashboard/business_customers.html', context)


@login_required(login_url='dashboard:login')
def customer_detail(request, customer_id):
    """
    Business owner view to see detailed customer information.
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
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('dashboard:home')
            
    except TenantCustomer.DoesNotExist:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:login')
    
    # Get the customer
    customer_rel = get_object_or_404(
        TenantCustomer,
        id=customer_id,
        tenant=tenant
    )
    
    # Get customer's transactions
    customer_transactions = []
    if TRANSACTIONS_ENABLED:
        customer_transactions = Transaction.objects.filter(
            tenant=tenant,
            customer=customer_rel.customer,
            status='completed'
        ).order_by('-transaction_date')[:10]
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'is_business_view': True,
        'customer_rel': customer_rel,
        'customer_transactions': customer_transactions,
    }
    
    return render(request, 'dashboard/business_customer_detail.html', context)


@login_required(login_url='dashboard:login')
def add_customer(request):
    """
    Business owner view to manually add a new customer.
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
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('dashboard:home')
            
    except TenantCustomer.DoesNotExist:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:login')
    
    if request.method == 'POST':
        form = BusinessCustomerAddForm(request.POST, tenant=tenant)
        if form.is_valid():
            new_customer = form.save()
            messages.success(
                request,
                f'Customer {new_customer.customer.get_full_name()} has been added successfully.'
            )
            return redirect('dashboard:customer_detail', customer_id=new_customer.id)
    else:
        form = BusinessCustomerAddForm(tenant=tenant)
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'is_business_view': True,
        'form': form,
    }
    
    return render(request, 'dashboard/business_customer_add.html', context)


@login_required(login_url='dashboard:login')
def edit_customer(request, customer_id):
    """
    Business owner view to edit existing customer information.
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
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('dashboard:home')
            
    except TenantCustomer.DoesNotExist:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:login')
    
    # Get the customer to edit
    customer_rel = get_object_or_404(
        TenantCustomer,
        id=customer_id,
        tenant=tenant
    )
    
    if request.method == 'POST':
        form = BusinessCustomerEditForm(
            request.POST, 
            instance=customer_rel,
            customer=customer_rel.customer
        )
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f'Customer {customer_rel.customer.get_full_name()} has been updated successfully.'
            )
            return redirect('dashboard:customer_detail', customer_id=customer_rel.id)
    else:
        form = BusinessCustomerEditForm(
            instance=customer_rel,
            customer=customer_rel.customer
        )
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'is_business_view': True,
        'form': form,
        'customer_rel': customer_rel,
    }
    
    return render(request, 'dashboard/business_customer_edit.html', context)


@login_required(login_url='dashboard:login')
def delete_customer(request, customer_id):
    """
    Business owner view to delete a customer (with confirmation).
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
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('dashboard:home')
            
    except TenantCustomer.DoesNotExist:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:login')
    
    # Get the customer to delete
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
        'status_filter': status_filter,
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