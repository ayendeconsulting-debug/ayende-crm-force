"""
Reports & Analytics Views
Business intelligence and reporting views for business owners
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Sum, Count, Avg, Q
from django.db.models.functions import TruncDate, TruncMonth, TruncHour
from django.utils import timezone
from datetime import datetime, timedelta
import csv
import json

from customers.models import Customer, TenantCustomer, Transaction
from .utils import (
    get_date_range,
    calculate_revenue_stats,
    calculate_growth_rate,
    get_revenue_by_period,
    calculate_customer_metrics,
    get_top_customers,
    calculate_loyalty_metrics,
    get_sales_analytics,
    export_to_csv,
    get_comparison_data,
    calculate_retention_rate,
)


def calculate_anonymous_metrics(transactions):
    """
    Calculate metrics for anonymous (walk-in) transactions.

    Args:
        transactions: QuerySet of Transaction objects

    Returns:
        dict with anonymous transaction metrics
    """
    from decimal import Decimal

    # Filter anonymous transactions
    anonymous_txs = transactions.filter(is_anonymous=True)
    customer_txs = transactions.filter(is_anonymous=False)

    total_count = transactions.count()
    anonymous_count = anonymous_txs.count()
    customer_count = customer_txs.count()

    # Calculate revenue
    anonymous_revenue = anonymous_txs.aggregate(
        total=Sum('total')
    )['total'] or Decimal('0')

    customer_revenue = customer_txs.aggregate(
        total=Sum('total')
    )['total'] or Decimal('0')

    total_revenue = anonymous_revenue + customer_revenue

    # Calculate percentages
    anonymous_pct = (anonymous_count / total_count * 100) if total_count > 0 else 0
    anonymous_revenue_pct = (float(anonymous_revenue) / float(total_revenue) * 100) if total_revenue > 0 else 0

    # Calculate average transaction values
    avg_anonymous = (anonymous_revenue / anonymous_count) if anonymous_count > 0 else Decimal('0')
    avg_customer = (customer_revenue / customer_count) if customer_count > 0 else Decimal('0')

    return {
        'anonymous_count': anonymous_count,
        'customer_count': customer_count,
        'total_count': total_count,
        'anonymous_percentage': round(anonymous_pct, 1),
        'customer_percentage': round(100 - anonymous_pct, 1),
        'anonymous_revenue': anonymous_revenue,
        'customer_revenue': customer_revenue,
        'total_revenue': total_revenue,
        'anonymous_revenue_percentage': round(anonymous_revenue_pct, 1),
        'customer_revenue_percentage': round(100 - anonymous_revenue_pct, 1),
        'avg_anonymous_value': avg_anonymous,
        'avg_customer_value': avg_customer,
    }


def check_staff_permission(request):
    """
    Helper function to check if user has staff permissions.
    Returns (tenant, tenant_customer) tuple or (None, None) if no access.
    """
    tenant = getattr(request, 'tenant', None)

    # Platform admins bypass tenant checks
    if hasattr(request.user, 'is_platform_admin') and request.user.is_platform_admin:
        return tenant, request.user

    if not tenant:
        return None, None

    # request.user IS already a TenantCustomer object
    tenant_customer = request.user

    # Verify user belongs to this tenant
    if tenant_customer.tenant != tenant:
        return None, None

    # Check if user has staff permissions
    if not tenant_customer.is_staff_member:
        return None, None

    return tenant, tenant_customer


@login_required(login_url='dashboard:login')
def reports_dashboard(request):
    """
    Enhanced Command Center dashboard with dense widgets and dark theme.
    Main reports and analytics dashboard.
    """
    tenant, tenant_customer = check_staff_permission(request)

    if not tenant:
        messages.error(request, 'You do not have permission to access reports.')
        return redirect('dashboard:home')

    # Get date range from request or default to last 30 days
    period = request.GET.get('period', 'month')
    start_date, end_date = get_date_range(period)

    # Get all data
    all_transactions = Transaction.objects.filter(
        tenant=tenant,
        status='completed'
    )

    period_transactions = all_transactions.filter(
        transaction_date__gte=start_date,
        transaction_date__lte=end_date
    )

    all_customers = TenantCustomer.objects.filter(
        tenant=tenant,
        role='customer'
    )

    # Get recent transactions for activity feed
    recent_transactions = period_transactions.order_by('-transaction_date')[:10]

    # Calculate key metrics
    revenue_stats = calculate_revenue_stats(period_transactions)
    customer_metrics = calculate_customer_metrics(all_customers, all_transactions)
    loyalty_metrics = calculate_loyalty_metrics(all_customers, all_transactions)
    sales_analytics = get_sales_analytics(period_transactions)
    
    # Calculate anonymous transaction metrics
    anonymous_metrics = calculate_anonymous_metrics(period_transactions)
    
    # Get comparison data
    comparison = get_comparison_data(all_transactions, start_date, end_date)
    
    # Calculate retention rate
    retention_rate = calculate_retention_rate(all_customers, days=30)
    
    # Get revenue trend data for chart
    revenue_by_day = get_revenue_by_period(period_transactions, 'day')
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'is_business_view': True,
        'period': period,
        'start_date': start_date,
        'end_date': end_date,
        'revenue_stats': revenue_stats,
        'customer_metrics': customer_metrics,
        'loyalty_metrics': loyalty_metrics,
        'sales_analytics': sales_analytics,
        'anonymous_metrics': anonymous_metrics,
        'comparison': comparison,
        'retention_rate': retention_rate,
        'revenue_by_day': json.dumps(revenue_by_day),
        'recent_transactions': recent_transactions,
        'currency_symbol': '$',
    }
    
    return render(request, 'reports/dashboard.html', context)

# REST OF THE FILE CONTINUES BELOW...
# (Keep all other functions: revenue_report, customer_report, sales_report, etc.)