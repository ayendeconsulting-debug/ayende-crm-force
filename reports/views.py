"""
Reports & Analytics Views
Business intelligence and reporting views for business owners
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Sum, Count, Avg, Q
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


def check_staff_permission(request):
    """
    Helper function to check if user has staff permissions.
    Returns (tenant, tenant_customer) tuple or (None, None) if no access.
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        return None, None
    
    try:
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
        
        if not tenant_customer.is_staff_member:
            return None, None
        
        return tenant, tenant_customer
    except TenantCustomer.DoesNotExist:
        return None, None


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
    
    # Customer acquisition trend
    acquisition_by_day = new_customers.extra(
        select={'day': "strftime('%%Y-%%m-%%d', joined_at)"}
    ).values('day').annotate(
        count=Count('id')
    ).order_by('day')
    
    acquisition_data = {
        item['day']: item['count']
        for item in acquisition_by_day
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
    volume_by_day = transactions.extra(
        select={'day': "strftime('%%Y-%%m-%%d', transaction_date)"}
    ).values('day').annotate(
        count=Count('id'),
        revenue=Sum('total')
    ).order_by('day')
    
    volume_data = {
        item['day']: item['count']
        for item in volume_by_day
    }
    
    # Average transaction value trend
    avg_value_by_day = {
        item['day']: float(item['revenue'] / item['count']) if item['count'] > 0 else 0
        for item in volume_by_day
    }
    
    # Peak hours analysis (if time data available)
    # Use strftime for SQLite compatibility
    hourly_sales = transactions.extra(
        select={'hour': "CAST(strftime('%%H', transaction_date) AS INTEGER)"}
    ).values('hour').annotate(
        count=Count('id'),
        revenue=Sum('total')
    ).order_by('hour')
    
    # Day of week analysis
    # Use strftime for SQLite compatibility (0=Sunday, 1=Monday, etc.)
    daily_sales = transactions.extra(
        select={'weekday': "CAST(strftime('%%w', transaction_date) AS INTEGER)"}
    ).values('weekday').annotate(
        count=Count('id'),
        revenue=Sum('total')
    ).order_by('weekday')
    
    weekday_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    daily_sales_formatted = [
        {
            'day': weekday_names[int(item['weekday'])],
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
    
    # Points issued over time
    # Use strftime for SQLite compatibility (works with both SQLite and PostgreSQL)
    points_by_month = all_transactions.extra(
        select={'month': "strftime('%%Y-%%m', transaction_date)"}
    ).values('month').annotate(
        points_issued=Sum('points_earned'),
        points_redeemed=Sum('points_redeemed')
    ).order_by('month')
    
    points_timeline = {
        item['month']: {
            'issued': item['points_issued'] or 0,
            'redeemed': item['points_redeemed'] or 0
        }
        for item in points_by_month
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
