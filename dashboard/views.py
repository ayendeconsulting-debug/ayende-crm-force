from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum, Count, Q, Avg
from django.utils import timezone
from django.http import JsonResponse
from datetime import timedelta
from customers.models import Customer, TenantCustomer
from .forms import (
    CustomerRegistrationForm, 
    CustomerLoginForm, 
    CustomerProfileForm,
    BusinessCustomerAddForm,
    BusinessCustomerEditForm,
    CustomerNotesForm
)

# Check if Transaction model exists, if not, skip transaction views
try:
    from customers.models import Transaction
    TRANSACTIONS_ENABLED = True
except ImportError:
    TRANSACTIONS_ENABLED = False


def customer_register(request):
    """
    Customer self-registration view.
    Automatically links customer to the current tenant.
    """
    # Redirect if already logged in
    if request.user.is_authenticated:
        return redirect('dashboard:home')
    
    # Get tenant from middleware
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to identify business. Please check the URL.')
        return redirect('/')
    
    # Check if tenant allows customer registration
    if not tenant.settings.allow_customer_registration:
        messages.error(request, 'Customer registration is currently disabled for this business.')
        return redirect('dashboard:login')
    
    if request.method == 'POST':
        form = CustomerRegistrationForm(request.POST, tenant=tenant)
        if form.is_valid():
            customer = form.save()
            # Automatically log in after registration
            login(request, customer, backend='tenants.backends.TenantAwareAuthBackend')
            messages.success(
                request,
                f'Welcome {customer.first_name}! Your account has been created successfully.'
            )
            return redirect('dashboard:home')
    else:
        form = CustomerRegistrationForm(tenant=tenant)
    
    context = {
        'form': form,
        'tenant': tenant
    }
    return render(request, 'dashboard/register.html', context)


def customer_login_view(request):
    """
    Customer login view with tenant-aware authentication.
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
            tenant=tenant,
            status='completed'
        )
        
        # Get aggregated stats
        stats = completed_transactions.aggregate(
            total_revenue=Sum('total'),
            transaction_count=Count('id')
        )
        
        total_revenue = stats['total_revenue'] or 0
        total_transactions = stats['transaction_count'] or 0
        
        # Calculate average transaction value
        if total_transactions > 0:
            avg_transaction_value = total_revenue / total_transactions
        
        # Get recent transactions with customer relationship
        recent_transactions = completed_transactions.select_related(
            'customer'
        ).order_by('-transaction_date')[:10]
        
        # CRITICAL FIX: Attach TenantCustomer to each transaction
        # This is what fixes the NoReverseMatch error
        for transaction in recent_transactions:
            try:
                # Find the TenantCustomer relationship for this transaction's customer
                transaction.tenant_customer = TenantCustomer.objects.get(
                    customer=transaction.customer,
                    tenant=tenant
                )
            except TenantCustomer.DoesNotExist:
                # If no relationship exists, set to None
                # Template will handle this gracefully
                transaction.tenant_customer = None
    
    # Top customers by loyalty points
    top_customers = all_customers.order_by('-loyalty_points')[:5]
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'is_business_view': True,
        'total_customers': total_customers,
        'new_customers': new_customers,
        'total_revenue': total_revenue,
        'total_transactions': total_transactions,
        'avg_transaction_value': avg_transaction_value,
        'recent_transactions': recent_transactions,
        'top_customers': top_customers,
    }
    return render(request, 'dashboard/business_home.html', context)


@login_required(login_url='dashboard:login')
def customer_profile(request):
    """
    Customer profile view and edit.
    """
    tenant = getattr(request, 'tenant', None)
    
    if request.method == 'POST':
        form = CustomerProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated successfully.')
            return redirect('dashboard:profile')
    else:
        form = CustomerProfileForm(instance=request.user)
    
    # Get customer-tenant relationship
    try:
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
    except TenantCustomer.DoesNotExist:
        tenant_customer = None
    
    context = {
        'form': form,
        'tenant': tenant,
        'tenant_customer': tenant_customer
    }
    return render(request, 'dashboard/profile.html', context)


# Transaction views - only available if Transaction model exists
if TRANSACTIONS_ENABLED:
    @login_required(login_url='dashboard:login')
    def transaction_history(request):
        """
        Display customer's transaction history.
        """
        tenant = getattr(request, 'tenant', None)
        
        if not tenant:
            messages.error(request, 'Unable to load transactions.')
            return redirect('dashboard:home')
        
        # Get customer-tenant relationship
        try:
            tenant_customer = TenantCustomer.objects.get(
                customer=request.user,
                tenant=tenant
            )
        except TenantCustomer.DoesNotExist:
            messages.error(request, 'You do not have access to this data.')
            return redirect('dashboard:login')
        
        # Get all transactions for this customer in this tenant
        transactions = Transaction.objects.filter(
            tenant=tenant,
            customer=request.user
        ).order_by('-transaction_date')
        
        # Filter by status if requested
        status_filter = request.GET.get('status')
        if status_filter:
            transactions = transactions.filter(status=status_filter)
        
        # Filter by date range if requested
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        if date_from:
            transactions = transactions.filter(transaction_date__gte=date_from)
        if date_to:
            transactions = transactions.filter(transaction_date__lte=date_to)
        
        # Pagination
        paginator = Paginator(transactions, 10)  # 10 transactions per page
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Calculate statistics
        total_spent = sum(t.total for t in transactions if t.status == 'completed')
        total_transactions = transactions.filter(status='completed').count()
        total_points_earned = sum(t.points_earned for t in transactions if t.status == 'completed')
        
        context = {
            'tenant': tenant,
            'tenant_customer': tenant_customer,
            'transactions': page_obj,
            'total_spent': total_spent,
            'total_transactions': total_transactions,
            'total_points_earned': total_points_earned,
            'status_filter': status_filter,
        }
        
        return render(request, 'dashboard/transactions.html', context)


    @login_required(login_url='dashboard:login')
    def transaction_detail(request, transaction_id):
        """
        Display detailed view of a single transaction.
        """
        tenant = getattr(request, 'tenant', None)
        
        if not tenant:
            messages.error(request, 'Unable to load transaction.')
            return redirect('dashboard:home')
        
        # Get transaction
        transaction = get_object_or_404(
            Transaction,
            transaction_id=transaction_id,
            tenant=tenant,
            customer=request.user
        )
        
        context = {
            'tenant': tenant,
            'transaction': transaction,
        }
        
        return render(request, 'dashboard/transaction_detail.html', context)

else:
    # Placeholder views if transactions not enabled
    @login_required(login_url='dashboard:login')
    def transaction_history(request):
        messages.warning(request, 'Transaction feature is not yet configured.')
        return redirect('dashboard:home')
    
    @login_required(login_url='dashboard:login')
    def transaction_detail(request, transaction_id):
        messages.warning(request, 'Transaction feature is not yet configured.')
        return redirect('dashboard:home')


# Business Owner Views
@login_required(login_url='dashboard:login')
def manage_customers(request):
    """
    Customer management page for business owners.
    List, search, filter customers.
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to load customer management.')
        return redirect('dashboard:home')
    
    # Get customer-tenant relationship and verify permissions
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
    
    # Get all customers for this tenant
    customers = TenantCustomer.objects.filter(
        tenant=tenant,
        role='customer'
    ).select_related('customer').order_by('-joined_at')
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        customers = customers.filter(
            Q(customer__first_name__icontains=search_query) |
            Q(customer__last_name__icontains=search_query) |
            Q(customer__email__icontains=search_query) |
            Q(customer__phone__icontains=search_query)
        )
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        customers = customers.filter(is_active=True)
    elif status_filter == 'inactive':
        customers = customers.filter(is_active=False)
    elif status_filter == 'vip':
        customers = customers.filter(is_vip=True)
    
    # Pagination
    paginator = Paginator(customers, 20)  # 20 customers per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'is_business_view': True,
        'customers': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'total_customers': customers.count(),
    }
    
    return render(request, 'dashboard/business_customers.html', context)


@login_required(login_url='dashboard:login')
def customer_detail_view(request, customer_id):
    """
    View detailed information about a specific customer.
    Business owners only.
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
