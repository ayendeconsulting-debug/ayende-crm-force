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
from tenants.models import Tenant
from decimal import Decimal
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
    Main reports and analytics dashboard.
    Overview of all key metrics with links to detailed reports.
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
    }
    
    return render(request, 'reports/dashboard.html', context)

@login_required(login_url='dashboard:login')
def revenue_report(request):
    """
    Detailed revenue report with charts and breakdowns.
    """
    tenant, tenant_customer = check_staff_permission(request)
    
    if not tenant:
        messages.error(request, 'You do not have permission to access reports.')
        return redirect('dashboard:home')
    
    # Get date range
    period = request.GET.get('period', 'month')
    start_date, end_date = get_date_range(period)
    
    # Get transactions
    transactions = Transaction.objects.filter(
        tenant=tenant,
        status='completed',
        transaction_date__gte=start_date,
        transaction_date__lte=end_date
    )
    
    # Calculate stats
    revenue_stats = calculate_revenue_stats(transactions)
    
    # Revenue by day/week/month
    revenue_by_day = get_revenue_by_period(transactions, 'day')
    
    # Revenue by payment method
    payment_breakdown = transactions.values('payment_method').annotate(
        total=Sum('total'),
        count=Count('id')
    ).order_by('-total')
    
    # Top revenue days
    top_days = transactions.values('transaction_date__date').annotate(
        revenue=Sum('total'),
        transactions=Count('id')
    ).order_by('-revenue')[:10]
    
    # Get comparison
    comparison = get_comparison_data(Transaction.objects.filter(tenant=tenant), start_date, end_date)
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'is_business_view': True,
        'period': period,
        'start_date': start_date,
        'end_date': end_date,
        'revenue_stats': revenue_stats,
        'revenue_by_day': json.dumps(revenue_by_day),
        'payment_breakdown': payment_breakdown,
        'top_days': top_days,
        'comparison': comparison,
    }
    
    return render(request, 'reports/revenue_report.html', context)


@login_required(login_url='dashboard:login')
def customer_report(request):
    """
    Customer insights and analysis report.
    """
    tenant, tenant_customer = check_staff_permission(request)
    
    if not tenant:
        messages.error(request, 'You do not have permission to access reports.')
        return redirect('dashboard:home')
    
    # Get date range
    period = request.GET.get('period', 'month')
    start_date, end_date = get_date_range(period)
    
    # Get all customers
    all_customers = TenantCustomer.objects.filter(
        tenant=tenant,
        role='customer'
    ).select_related('customer')
    
    # New customers in period
    new_customers = all_customers.filter(
        joined_at__gte=start_date,
        joined_at__lte=end_date
    )
    
    # Get all transactions
    all_transactions = Transaction.objects.filter(
        tenant=tenant,
        status='completed'
    )
    
    # Calculate metrics
    customer_metrics = calculate_customer_metrics(all_customers, all_transactions)
    
    # Top customers
    top_customers = get_top_customers(all_customers, limit=10)
    
    # Customer acquisition trend - PostgreSQL compatible
    acquisition_by_day = new_customers.annotate(
        day=TruncDate('joined_at')
    ).values('day').annotate(
        count=Count('id')
    ).order_by('day')
    
    acquisition_data = {
        item['day'].strftime('%Y-%m-%d'): item['count']
        for item in acquisition_by_day if item['day']
    }
    
    # Retention rate
    retention_rate = calculate_retention_rate(all_customers, days=30)
    
    # Customer segmentation by spending
    spending_segments = [
        {'name': 'High Value', 'min': 1000, 'customers': all_customers.filter(total_spent__gte=1000).count()},
        {'name': 'Medium Value', 'min': 500, 'customers': all_customers.filter(total_spent__gte=500, total_spent__lt=1000).count()},
        {'name': 'Low Value', 'min': 100, 'customers': all_customers.filter(total_spent__gte=100, total_spent__lt=500).count()},
        {'name': 'New/Inactive', 'min': 0, 'customers': all_customers.filter(total_spent__lt=100).count()},
    ]
    
    # Average purchase frequency
    active_customers = all_customers.filter(purchase_count__gt=0)
    if active_customers.exists():
        avg_purchase_frequency = active_customers.aggregate(
            Avg('purchase_count')
        )['purchase_count__avg']
    else:
        avg_purchase_frequency = 0
    
    # Get recent transactions for display
    recent_transactions = all_transactions.order_by('-transaction_date')[:10]
    
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'is_business_view': True,
        'period': period,
        'start_date': start_date,
        'end_date': end_date,
        'customer_metrics': customer_metrics,
        'top_customers': top_customers,
        'new_customers_count': new_customers.count(),
        'acquisition_data': json.dumps(acquisition_data),
        'retention_rate': retention_rate,
        'spending_segments': spending_segments,
        'avg_purchase_frequency': avg_purchase_frequency,
        'recent_transactions': recent_transactions,
        'currency_symbol': '$',
    }
    
    return render(request, 'reports/customer_report.html', context)


@login_required(login_url='dashboard:login')
def sales_report(request):
    """
    Sales analytics and transaction insights.
    """
    tenant, tenant_customer = check_staff_permission(request)
    
    if not tenant:
        messages.error(request, 'You do not have permission to access reports.')
        return redirect('dashboard:home')
    
    # Get date range
    period = request.GET.get('period', 'month')
    start_date, end_date = get_date_range(period)
    
    # Get transactions
    transactions = Transaction.objects.filter(
        tenant=tenant,
        status='completed',
        transaction_date__gte=start_date,
        transaction_date__lte=end_date
    )
    
    # Sales analytics
    sales_analytics = get_sales_analytics(transactions)
    
    # Transaction volume by day
    volume_by_day = transactions.annotate(
        day=TruncDate('transaction_date')
    ).values('day').annotate(
        count=Count('id'),
        revenue=Sum('total')
    ).order_by('day')
    
    volume_data = {
        item['day'].strftime('%Y-%m-%d'): item['count']
        for item in volume_by_day if item['day']
    }
    
    # Average transaction value trend
    avg_value_by_day = {
        item['day'].strftime('%Y-%m-%d'): float(item['revenue'] / item['count']) if item['count'] > 0 else 0
        for item in volume_by_day if item['day']
    }
    
    # Peak hours analysis (if time data available)
    # PostgreSQL compatible
    hourly_sales = transactions.annotate(
        hour=TruncHour('transaction_date')
    ).values('hour').annotate(
        count=Count('id'),
        revenue=Sum('total')
    ).order_by('hour')
    
    # Day of week analysis - PostgreSQL compatible
    from django.db.models.functions import ExtractWeekDay
    daily_sales = transactions.annotate(
        weekday=ExtractWeekDay('transaction_date')
    ).values('weekday').annotate(
        count=Count('id'),
        revenue=Sum('total')
    ).order_by('weekday')
    
    weekday_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    daily_sales_formatted = [
        {
            'day': weekday_names[(int(item['weekday']) - 1) % 7],
            'count': item['count'],
            'revenue': item['revenue']
        }
        for item in daily_sales
    ]
    
    # Calculate stats
    revenue_stats = calculate_revenue_stats(transactions)
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'is_business_view': True,
        'period': period,
        'start_date': start_date,
        'end_date': end_date,
        'sales_analytics': sales_analytics,
        'revenue_stats': revenue_stats,
        'volume_data': json.dumps(volume_data),
        'avg_value_data': json.dumps(avg_value_by_day),
        'hourly_sales': hourly_sales,
        'daily_sales': daily_sales_formatted,
    }
    
    return render(request, 'reports/sales_report.html', context)


@login_required(login_url='dashboard:login')
def loyalty_report(request):
    """
    Loyalty program effectiveness and metrics.
    """
    tenant, tenant_customer = check_staff_permission(request)
    
    if not tenant:
        messages.error(request, 'You do not have permission to access reports.')
        return redirect('dashboard:home')
    
    # Get all customers
    all_customers = TenantCustomer.objects.filter(
        tenant=tenant,
        role='customer'
    ).select_related('customer')
    
    # Get all transactions
    all_transactions = Transaction.objects.filter(
        tenant=tenant,
        status='completed'
    )
    
    # Calculate loyalty metrics
    loyalty_metrics = calculate_loyalty_metrics(all_customers, all_transactions)
    
    # Points distribution
    points_ranges = [
        {'range': '0-100', 'min': 0, 'max': 100},
        {'range': '101-500', 'min': 101, 'max': 500},
        {'range': '501-1000', 'min': 501, 'max': 1000},
        {'range': '1000+', 'min': 1001, 'max': 999999},
    ]
    
    for range_item in points_ranges:
        range_item['count'] = all_customers.filter(
            loyalty_points__gte=range_item['min'],
            loyalty_points__lte=range_item['max']
        ).count()
    
    # Top point earners
    top_earners = all_customers.filter(
        loyalty_points__gt=0
    ).order_by('-loyalty_points')[:10]
    
    # Points issued over time - PostgreSQL compatible
    points_by_month = all_transactions.annotate(
        month=TruncMonth('transaction_date')
    ).values('month').annotate(
        points_issued=Sum('points_earned'),
        points_redeemed=Sum('points_redeemed')
    ).order_by('month')
    
    points_timeline = {
        item['month'].strftime('%Y-%m'): {
            'issued': item['points_issued'] or 0,
            'redeemed': item['points_redeemed'] or 0
        }
        for item in points_by_month if item['month']
    }
    
    # Check if rewards app is available
    try:
        from rewards.models import Redemption
        
        # Most popular rewards
        popular_rewards = Redemption.objects.filter(
            tenant=tenant,
            status__in=['approved', 'used']
        ).values('reward__name').annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        rewards_available = True
    except ImportError:
        popular_rewards = []
        rewards_available = False
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'is_business_view': True,
        'loyalty_metrics': loyalty_metrics,
        'points_ranges': points_ranges,
        'top_earners': top_earners,
        'points_timeline': json.dumps(points_timeline),
        'popular_rewards': popular_rewards,
        'rewards_available': rewards_available,
    }
    
    return render(request, 'reports/loyalty_report.html', context)


@login_required(login_url='dashboard:login')
def export_revenue_csv(request):
    """
    Export revenue report to CSV.
    """
    tenant, tenant_customer = check_staff_permission(request)
    
    if not tenant:
        messages.error(request, 'You do not have permission to export reports.')
        return redirect('dashboard:home')
    
    # Get date range
    period = request.GET.get('period', 'month')
    start_date, end_date = get_date_range(period)
    
    # Get transactions
    transactions = Transaction.objects.filter(
        tenant=tenant,
        status='completed',
        transaction_date__gte=start_date,
        transaction_date__lte=end_date
    ).select_related('customer')
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="revenue_report_{start_date.date()}_to_{end_date.date()}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Transaction Date', 'Transaction ID', 'Customer', 'Amount', 'Tax', 'Total', 'Payment Method', 'Points Earned'])
    
    for txn in transactions:
        writer.writerow([
            txn.transaction_date.strftime('%Y-%m-%d %H:%M'),
            txn.transaction_id,
            txn.customer.get_full_name(),
            f'{txn.amount:.2f}',
            f'{txn.tax:.2f}',
            f'{txn.total:.2f}',
            txn.get_payment_method_display(),
            txn.points_earned,
        ])
    
    # Add summary row
    writer.writerow([])
    writer.writerow(['SUMMARY'])
    
    stats = calculate_revenue_stats(transactions)
    writer.writerow(['Total Revenue', f"${stats['total_revenue']:.2f}"])
    writer.writerow(['Total Transactions', stats['total_transactions']])
    writer.writerow(['Average Transaction', f"${stats['avg_transaction']:.2f}"])
    writer.writerow(['Total Tax', f"${stats['total_tax']:.2f}"])
    
    return response


@login_required(login_url='dashboard:login')
def export_customers_csv(request):
    """
    Export customer report to CSV.
    """
    tenant, tenant_customer = check_staff_permission(request)
    
    if not tenant:
        messages.error(request, 'You do not have permission to export reports.')
        return redirect('dashboard:home')
    
    # Get all customers
    customers = TenantCustomer.objects.filter(
        tenant=tenant,
        role='customer'
    ).select_related('customer').order_by('-total_spent')
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="customers_report_{timezone.now().date()}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Name', 'Email', 'Phone', 'Loyalty Points', 'Total Spent', 'Purchase Count', 'VIP Status', 'Joined Date', 'Last Purchase'])
    
    for tc in customers:
        writer.writerow([
            tc.customer.get_full_name(),
            tc.customer.email,
            tc.customer.phone,
            tc.loyalty_points,
            f'{tc.total_spent:.2f}',
            tc.purchase_count,
            'Yes' if tc.is_vip else 'No',
            tc.joined_at.strftime('%Y-%m-%d'),
            tc.last_purchase_at.strftime('%Y-%m-%d') if tc.last_purchase_at else 'Never',
        ])
    
    return response


@login_required(login_url='dashboard:login')
def print_report(request, report_type):
    """
    Generate printable version of report.
    """
    tenant, tenant_customer = check_staff_permission(request)
    
    if not tenant:
        messages.error(request, 'You do not have permission to access reports.')
        return redirect('dashboard:home')
    
    # Redirect to appropriate report with print parameter
    if report_type == 'revenue':
        return redirect(f"{request.path}?print=true")
    elif report_type == 'customers':
        return redirect(f"{request.path}?print=true")
    elif report_type == 'sales':
        return redirect(f"{request.path}?print=true")
    elif report_type == 'loyalty':
        return redirect(f"{request.path}?print=true")
    else:
        messages.error(request, 'Invalid report type.')
        return redirect('reports:dashboard')
    
@login_required(login_url='dashboard:login')
def platform_dashboard(request):
    """
    Platform admin dashboard - system-wide view of all tenants.
    Only accessible to platform administrators.
    """
    # Check if user is platform admin
    if not hasattr(request.user, 'is_platform_admin') or not request.user.is_platform_admin:
        messages.error(request, 'Access denied. Platform admin privileges required.')
        return redirect('dashboard:home')
    
    # Get date range (default last 30 days)
    period = request.GET.get('period', 'month')
    if period == 'today':
        start_date = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = timezone.now()
    elif period == 'week':
        start_date = timezone.now() - timedelta(days=7)
        end_date = timezone.now()
    elif period == 'month':
        start_date = timezone.now() - timedelta(days=30)
        end_date = timezone.now()
    elif period == 'quarter':
        start_date = timezone.now() - timedelta(days=90)
        end_date = timezone.now()
    elif period == 'year':
        start_date = timezone.now() - timedelta(days=365)
        end_date = timezone.now()
    else:
        start_date = timezone.now() - timedelta(days=30)
        end_date = timezone.now()
    
    # Total tenants
    all_tenants = Tenant.objects.all()
    total_tenants = all_tenants.count()
    active_tenants = all_tenants.filter(is_active=True).count()
    
    # New tenants in period
    new_tenants = all_tenants.filter(
        created_at__gte=start_date,
        created_at__lte=end_date
    ).count()
    
    # Total customers across all tenants
    all_customers = TenantCustomer.objects.filter(role='customer')
    total_customers = all_customers.count()
    
    # New customers in period
    new_customers = all_customers.filter(
        joined_at__gte=start_date,
        joined_at__lte=end_date
    ).count()
    
    # Total transactions
    all_transactions = Transaction.objects.filter(status='completed')
    total_transactions = all_transactions.count()
    
    # Transactions in period
    period_transactions = all_transactions.filter(
        transaction_date__gte=start_date,
        transaction_date__lte=end_date
    )
    period_transaction_count = period_transactions.count()
    
    # Total revenue (all time)
    total_revenue = all_transactions.aggregate(
        total=Sum('total')
    )['total'] or Decimal('0')
    
    # Revenue in period
    period_revenue = period_transactions.aggregate(
        total=Sum('total')
    )['total'] or Decimal('0')
    
    # Average revenue per tenant
    avg_revenue_per_tenant = (total_revenue / total_tenants) if total_tenants > 0 else Decimal('0')
    
    # Average transaction value
    avg_transaction_value = (period_revenue / period_transaction_count) if period_transaction_count > 0 else Decimal('0')
    
    # Total loyalty points issued
    total_loyalty_points = all_customers.aggregate(
        total=Sum('loyalty_points')
    )['total'] or 0
    
    # Active users today (had transaction today)
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    active_users_today = Transaction.objects.filter(
        transaction_date__gte=today_start,
        status='completed'
    ).values('tenant_customer').distinct().count()
    
    # Top tenants by revenue
    tenant_performance = []
    for tenant in all_tenants:
        tenant_transactions = Transaction.objects.filter(
            tenant=tenant,
            status='completed'
        )
        
        tenant_revenue = tenant_transactions.aggregate(
            total=Sum('total')
        )['total'] or Decimal('0')
        
        tenant_customer_count = TenantCustomer.objects.filter(
            tenant=tenant,
            role='customer'
        ).count()
        
        tenant_transaction_count = tenant_transactions.count()
        
        tenant_performance.append({
            'tenant': tenant,
            'revenue': tenant_revenue,
            'customers': tenant_customer_count,
            'transactions': tenant_transaction_count,
            'avg_transaction': (tenant_revenue / tenant_transaction_count) if tenant_transaction_count > 0 else Decimal('0')
        })
    
    # Sort by revenue
    tenant_performance.sort(key=lambda x: x['revenue'], reverse=True)
    top_tenants = tenant_performance[:10]
    
    # Calculate previous period for comparison
    period_length = (end_date - start_date).days
    previous_start = start_date - timedelta(days=period_length)
    previous_end = start_date
    
    previous_revenue = Transaction.objects.filter(
        status='completed',
        transaction_date__gte=previous_start,
        transaction_date__lte=previous_end
    ).aggregate(total=Sum('total'))['total'] or Decimal('0')
    
    previous_transactions = Transaction.objects.filter(
        status='completed',
        transaction_date__gte=previous_start,
        transaction_date__lte=previous_end
    ).count()
    
    # Calculate growth rates
    revenue_growth = 0
    if previous_revenue > 0:
        revenue_growth = float((period_revenue - previous_revenue) / previous_revenue * 100)
    
    transaction_growth = 0
    if previous_transactions > 0:
        transaction_growth = float((period_transaction_count - previous_transactions) / previous_transactions * 100)
    
    # Revenue by day
    revenue_by_day = period_transactions.annotate(
        day=TruncDate('transaction_date')
    ).values('day').annotate(
        revenue=Sum('total')
    ).order_by('day')
    
    revenue_chart_data = {
        item['day'].strftime('%Y-%m-%d'): float(item['revenue'])
        for item in revenue_by_day if item['day']
    }
    
    # Tenant distribution by customer count
    tenant_distribution = [
        {'name': '0-10 customers', 'count': 0},
        {'name': '11-50 customers', 'count': 0},
        {'name': '51-100 customers', 'count': 0},
        {'name': '100+ customers', 'count': 0},
    ]
    
    for tenant in all_tenants:
        customer_count = TenantCustomer.objects.filter(
            tenant=tenant,
            role='customer'
        ).count()
        
        if customer_count <= 10:
            tenant_distribution[0]['count'] += 1
        elif customer_count <= 50:
            tenant_distribution[1]['count'] += 1
        elif customer_count <= 100:
            tenant_distribution[2]['count'] += 1
        else:
            tenant_distribution[3]['count'] += 1
    
    # Recent tenant registrations
    recent_tenants = all_tenants.order_by('-created_at')[:10]
    
    # Low activity tenants (no transactions in last 7 days)
    seven_days_ago = timezone.now() - timedelta(days=7)
    low_activity_tenants = []
    
    for tenant in all_tenants:
        recent_txs = Transaction.objects.filter(
            tenant=tenant,
            transaction_date__gte=seven_days_ago
        ).count()
        
        if recent_txs == 0:
            low_activity_tenants.append(tenant)
    
    context = {
        'is_platform_admin': True,
        'period': period,
        'start_date': start_date,
        'end_date': end_date,
        'total_tenants': total_tenants,
        'active_tenants': active_tenants,
        'new_tenants': new_tenants,
        'total_customers': total_customers,
        'new_customers': new_customers,
        'total_transactions': total_transactions,
        'period_transaction_count': period_transaction_count,
        'total_revenue': total_revenue,
        'period_revenue': period_revenue,
        'avg_revenue_per_tenant': avg_revenue_per_tenant,
        'avg_transaction_value': avg_transaction_value,
        'total_loyalty_points': total_loyalty_points,
        'active_users_today': active_users_today,
        'revenue_growth': revenue_growth,
        'transaction_growth': transaction_growth,
        'top_tenants': top_tenants,
        'tenant_distribution': tenant_distribution,
        'revenue_chart_data': json.dumps(revenue_chart_data),
        'recent_tenants': recent_tenants,
        'low_activity_tenants': low_activity_tenants,
        'low_activity_count': len(low_activity_tenants),
        'currency_symbol': '$',
    }
    
    return render(request, 'platform/dashboard.html', context)

@login_required(login_url='dashboard:login')
def platform_revenue_dashboard(request):
    """
    Platform Revenue Dashboard - Shows income from tenant subscriptions and fees.
    Only accessible to platform administrators.
    """
    # Check if user is platform admin
    if not hasattr(request.user, 'is_platform_admin') or not request.user.is_platform_admin:
        messages.error(request, 'Access denied. Platform admin privileges required.')
        return redirect('dashboard:home')
    
    # Import models (avoid circular import)
    from billing.models import (
        SubscriptionPlan, TenantSubscription, ProfessionalFee,
        PlatformInvoice, PlatformPayment, RevenueMetrics
    )
    from tenants.models import Tenant
    
    # Get date range
    period = request.GET.get('period', 'month')
    if period == 'today':
        start_date = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = timezone.now()
    elif period == 'week':
        start_date = timezone.now() - timedelta(days=7)
        end_date = timezone.now()
    elif period == 'month':
        start_date = timezone.now() - timedelta(days=30)
        end_date = timezone.now()
    elif period == 'quarter':
        start_date = timezone.now() - timedelta(days=90)
        end_date = timezone.now()
    elif period == 'year':
        start_date = timezone.now() - timedelta(days=365)
        end_date = timezone.now()
    else:
        start_date = timezone.now() - timedelta(days=30)
        end_date = timezone.now()
    
    # ===================================
    # SUBSCRIPTION METRICS
    # ===================================
    
    # Current MRR (Monthly Recurring Revenue)
    active_subscriptions = TenantSubscription.objects.filter(
        status__in=['trial', 'active']
    )
    
    total_mrr = Decimal('0')
    for sub in active_subscriptions:
        total_mrr += sub.calculate_mrr()
    
    # ARR (Annual Recurring Revenue)
    total_arr = total_mrr * 12
    
    # Subscription breakdown by status
    trial_count = TenantSubscription.objects.filter(status='trial').count()
    active_count = TenantSubscription.objects.filter(status='active').count()
    past_due_count = TenantSubscription.objects.filter(status='past_due').count()
    canceled_count = TenantSubscription.objects.filter(status='canceled').count()
    
    # Subscription breakdown by plan
    plan_breakdown = []
    for plan in SubscriptionPlan.objects.filter(is_active=True):
        sub_count = TenantSubscription.objects.filter(
            plan=plan,
            status__in=['trial', 'active']
        ).count()
        
        plan_mrr = Decimal('0')
        for sub in TenantSubscription.objects.filter(plan=plan, status__in=['trial', 'active']):
            plan_mrr += sub.calculate_mrr()
        
        plan_breakdown.append({
            'plan': plan,
            'subscribers': sub_count,
            'mrr': plan_mrr,
            'percentage': (plan_mrr / total_mrr * 100) if total_mrr > 0 else 0
        })
    
    # New subscriptions in period
    new_subscriptions = TenantSubscription.objects.filter(
        created_at__gte=start_date,
        created_at__lte=end_date
    ).count()
    
    # Canceled subscriptions in period
    canceled_in_period = TenantSubscription.objects.filter(
        canceled_at__gte=start_date,
        canceled_at__lte=end_date
    ).count()
    
    # Churn rate
    churn_rate = 0
    if active_count > 0:
        churn_rate = (canceled_in_period / active_count) * 100
    
    # ===================================
    # REVENUE METRICS
    # ===================================
    
    # Professional fees in period
    professional_fees = ProfessionalFee.objects.filter(
        service_date__gte=start_date.date(),
        service_date__lte=end_date.date(),
        status='paid'
    )
    
    professional_fees_total = professional_fees.aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0')
    
    # Payments received in period
    payments = PlatformPayment.objects.filter(
        payment_date__gte=start_date,
        payment_date__lte=end_date,
        status='completed'
    )
    
    period_revenue = payments.aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0')
    
    # Total revenue (all time)
    total_revenue_all_time = PlatformPayment.objects.filter(
        status='completed'
    ).aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0')
    
    # Average revenue per tenant
    total_tenants = Tenant.objects.filter(is_active=True).count()
    avg_revenue_per_tenant = (total_revenue_all_time / total_tenants) if total_tenants > 0 else Decimal('0')
    
    # ===================================
    # INVOICE METRICS
    # ===================================
    
    # Outstanding invoices
    outstanding_invoices = PlatformInvoice.objects.filter(
        status__in=['sent', 'overdue']
    )
    
    outstanding_amount = outstanding_invoices.aggregate(
        total=Sum('total_amount')
    )['total'] or Decimal('0')
    
    # Overdue invoices
    overdue_invoices = PlatformInvoice.objects.filter(status='overdue')
    overdue_amount = overdue_invoices.aggregate(
        total=Sum('total_amount')
    )['total'] or Decimal('0')
    
    # Paid invoices in period
    paid_invoices_count = PlatformInvoice.objects.filter(
        paid_date__gte=start_date.date(),
        paid_date__lte=end_date.date(),
        status='paid'
    ).count()
    
    # ===================================
    # GROWTH METRICS
    # ===================================
    
    # Calculate previous period
    period_length = (end_date - start_date).days
    previous_start = start_date - timedelta(days=period_length)
    previous_end = start_date
    
    # Previous period revenue
    previous_payments = PlatformPayment.objects.filter(
        payment_date__gte=previous_start,
        payment_date__lte=previous_end,
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    # Revenue growth
    revenue_growth = 0
    if previous_payments > 0:
        revenue_growth = float((period_revenue - previous_payments) / previous_payments * 100)
    
    # MRR growth (compare current vs 30 days ago)
    # This is simplified - you'd want to store historical MRR in RevenueMetrics
    mrr_growth = 0  # Placeholder - implement with RevenueMetrics table
    
    # ===================================
    # CHARTS DATA
    # ===================================
    
    # Revenue by day
    daily_revenue = payments.annotate(
        day=TruncDate('payment_date')
    ).values('day').annotate(
        revenue=Sum('amount')
    ).order_by('day')
    
    revenue_chart_data = {
        item['day'].strftime('%Y-%m-%d'): float(item['revenue'])
        for item in daily_revenue if item['day']
    }
    
    # MRR trend (last 12 months)
    # Simplified - would use RevenueMetrics table for historical data
    mrr_trend_data = {}
    
    # Revenue by plan
    plan_revenue_data = {
        item['plan'].name: float(item['mrr'])
        for item in plan_breakdown
    }
    
    # ===================================
    # TOP CUSTOMERS (by revenue)
    # ===================================
    
    top_tenants_by_revenue = []
    for tenant in Tenant.objects.filter(is_active=True):
        tenant_payments = PlatformPayment.objects.filter(
            tenant=tenant,
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        try:
            subscription = tenant.subscription
            current_plan = subscription.plan.name
            sub_status = subscription.status
        except:
            current_plan = 'No subscription'
            sub_status = 'none'
        
        if tenant_payments > 0:
            top_tenants_by_revenue.append({
                'tenant': tenant,
                'revenue': tenant_payments,
                'plan': current_plan,
                'status': sub_status
            })
    
    # Sort by revenue
    top_tenants_by_revenue.sort(key=lambda x: x['revenue'], reverse=True)
    top_tenants = top_tenants_by_revenue[:10]
    
    # ===================================
    # RECENT ACTIVITY
    # ===================================
    
    # Recent payments
    recent_payments = PlatformPayment.objects.filter(
        status='completed'
    ).order_by('-payment_date')[:10]
    
    # Recent invoices
    recent_invoices = PlatformInvoice.objects.order_by('-created_at')[:10]
    
    # Upcoming renewals (next 30 days)
    thirty_days_from_now = timezone.now().date() + timedelta(days=30)
    upcoming_renewals = TenantSubscription.objects.filter(
        status='active',
        next_billing_date__lte=thirty_days_from_now,
        next_billing_date__gte=timezone.now().date()
    ).order_by('next_billing_date')[:10]
    
    # ===================================
    # CONTEXT
    # ===================================
    
    context = {
        'is_platform_admin': True,
        'period': period,
        'start_date': start_date,
        'end_date': end_date,
        
        # Subscription metrics
        'total_mrr': total_mrr,
        'total_arr': total_arr,
        'mrr_growth': mrr_growth,
        'trial_count': trial_count,
        'active_count': active_count,
        'past_due_count': past_due_count,
        'canceled_count': canceled_count,
        'new_subscriptions': new_subscriptions,
        'canceled_in_period': canceled_in_period,
        'churn_rate': churn_rate,
        
        # Revenue metrics
        'period_revenue': period_revenue,
        'total_revenue_all_time': total_revenue_all_time,
        'professional_fees_total': professional_fees_total,
        'avg_revenue_per_tenant': avg_revenue_per_tenant,
        'revenue_growth': revenue_growth,
        
        # Invoice metrics
        'outstanding_amount': outstanding_amount,
        'overdue_amount': overdue_amount,
        'outstanding_invoices_count': outstanding_invoices.count(),
        'overdue_invoices_count': overdue_invoices.count(),
        'paid_invoices_count': paid_invoices_count,
        
        # Breakdowns
        'plan_breakdown': plan_breakdown,
        'top_tenants': top_tenants,
        
        # Charts
        'revenue_chart_data': json.dumps(revenue_chart_data),
        'plan_revenue_data': json.dumps(plan_revenue_data),
        
        # Activity
        'recent_payments': recent_payments,
        'recent_invoices': recent_invoices,
        'upcoming_renewals': upcoming_renewals,
        
        'currency_symbol': '$',
    }
    
    return render(request, 'platform/revenue_dashboard.html', context)