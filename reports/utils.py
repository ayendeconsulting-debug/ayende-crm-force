"""
Utility functions for reports and analytics
Helper functions for data aggregation, calculations, and formatting
"""

from django.db.models import Sum, Count, Avg, Q, F
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
import csv
from io import StringIO


def get_date_range(period='month', custom_start=None, custom_end=None):
    """
    Get start and end dates for a given period.
    
    Args:
        period: 'today', 'week', 'month', 'quarter', 'year', 'custom'
        custom_start: Start date for custom range
        custom_end: End date for custom range
    
    Returns:
        tuple: (start_date, end_date)
    """
    now = timezone.now()
    
    if period == 'today':
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now
    elif period == 'week':
        start = now - timedelta(days=7)
        end = now
    elif period == 'month':
        start = now - timedelta(days=30)
        end = now
    elif period == 'quarter':
        start = now - timedelta(days=90)
        end = now
    elif period == 'year':
        start = now - timedelta(days=365)
        end = now
    elif period == 'custom' and custom_start and custom_end:
        start = custom_start
        end = custom_end
    else:
        # Default to last 30 days
        start = now - timedelta(days=30)
        end = now
    
    return start, end


def calculate_revenue_stats(transactions):
    """
    Calculate revenue statistics from transactions.
    
    Args:
        transactions: QuerySet of Transaction objects
    
    Returns:
        dict: Revenue statistics
    """
    stats = transactions.aggregate(
        total_revenue=Sum('total'),
        total_transactions=Count('id'),
        avg_transaction=Avg('total'),
        total_tax=Sum('tax')
    )
    
    return {
        'total_revenue': stats['total_revenue'] or 0,
        'total_transactions': stats['total_transactions'] or 0,
        'avg_transaction': stats['avg_transaction'] or 0,
        'total_tax': stats['total_tax'] or 0,
    }


def calculate_growth_rate(current_value, previous_value):
    """
    Calculate percentage growth rate.
    
    Args:
        current_value: Current period value
        previous_value: Previous period value
    
    Returns:
        float: Growth rate percentage
    """
    if previous_value == 0:
        return 100.0 if current_value > 0 else 0.0
    
    growth = ((current_value - previous_value) / previous_value) * 100
    return round(growth, 2)


def get_revenue_by_period(transactions, period_type='day'):
    """
    Group revenue by time period (day, week, month).
    
    Args:
        transactions: QuerySet of Transaction objects
        period_type: 'day', 'week', or 'month'
    
    Returns:
        dict: {period_label: revenue_amount}
    """
    from django.db.models.functions import TruncDay, TruncWeek, TruncMonth
    
    if period_type == 'day':
        trunc_func = TruncDay
    elif period_type == 'week':
        trunc_func = TruncWeek
    else:
        trunc_func = TruncMonth
    
    revenue_data = transactions.annotate(
        period=trunc_func('transaction_date')
    ).values('period').annotate(
        revenue=Sum('total')
    ).order_by('period')
    
    return {
        item['period'].strftime('%Y-%m-%d'): float(item['revenue'])
        for item in revenue_data
    }


def calculate_customer_metrics(tenant_customers, transactions):
    """
    Calculate customer-related metrics.
    
    Args:
        tenant_customers: QuerySet of TenantCustomer objects
        transactions: QuerySet of Transaction objects
    
    Returns:
        dict: Customer metrics
    """
    total_customers = tenant_customers.filter(role='customer').count()
    active_customers = tenant_customers.filter(
        role='customer',
        is_active=True
    ).count()
    vip_customers = tenant_customers.filter(
        role='customer',
        is_vip=True
    ).count()
    
    # Customer lifetime value
    if total_customers > 0:
        total_revenue = transactions.aggregate(Sum('total'))['total__sum'] or 0
        avg_customer_value = total_revenue / total_customers
    else:
        avg_customer_value = 0
    
    return {
        'total_customers': total_customers,
        'active_customers': active_customers,
        'vip_customers': vip_customers,
        'avg_customer_value': avg_customer_value,
    }


def get_top_customers(tenant_customers, limit=10):
    """
    Get top customers by various metrics.
    
    Args:
        tenant_customers: QuerySet of TenantCustomer objects
        limit: Number of customers to return
    
    Returns:
        dict: Top customers by different metrics
    """
    return {
        'by_points': tenant_customers.filter(
            role='customer'
        ).order_by('-loyalty_points')[:limit],
        
        'by_spend': tenant_customers.filter(
            role='customer'
        ).order_by('-total_spent')[:limit],
        
        'by_purchases': tenant_customers.filter(
            role='customer'
        ).order_by('-purchase_count')[:limit],
    }


def calculate_loyalty_metrics(tenant_customers, transactions):
    """
    Calculate loyalty program effectiveness metrics.
    
    Args:
        tenant_customers: QuerySet of TenantCustomer objects
        transactions: QuerySet of Transaction objects
    
    Returns:
        dict: Loyalty program metrics
    """
    # Total points issued
    total_points_issued = transactions.aggregate(
        Sum('points_earned')
    )['points_earned__sum'] or 0
    
    # Total points redeemed
    total_points_redeemed = transactions.aggregate(
        Sum('points_redeemed')
    )['points_redeemed__sum'] or 0
    
    # Current points balance
    current_points_balance = tenant_customers.aggregate(
        Sum('loyalty_points')
    )['loyalty_points__sum'] or 0
    
    # Redemption rate
    if total_points_issued > 0:
        redemption_rate = (total_points_redeemed / total_points_issued) * 100
    else:
        redemption_rate = 0
    
    # Active participants (customers with points > 0)
    active_participants = tenant_customers.filter(
        loyalty_points__gt=0
    ).count()
    
    return {
        'total_points_issued': total_points_issued,
        'total_points_redeemed': total_points_redeemed,
        'current_points_balance': current_points_balance,
        'redemption_rate': round(redemption_rate, 2),
        'active_participants': active_participants,
    }


def get_sales_analytics(transactions):
    """
    Calculate sales analytics and trends.
    
    Args:
        transactions: QuerySet of Transaction objects
    
    Returns:
        dict: Sales analytics
    """
    # Payment method breakdown
    payment_methods = transactions.values('payment_method').annotate(
        count=Count('id'),
        revenue=Sum('total')
    ).order_by('-revenue')
    
    # Transaction status breakdown
    status_breakdown = transactions.values('status').annotate(
        count=Count('id')
    )
    
    # Average items per transaction (if items_description exists)
    avg_items = transactions.exclude(
        items_description=''
    ).count()
    
    return {
        'payment_methods': list(payment_methods),
        'status_breakdown': list(status_breakdown),
        'total_completed': transactions.filter(status='completed').count(),
        'total_pending': transactions.filter(status='pending').count(),
        'total_cancelled': transactions.filter(status='cancelled').count(),
    }


def export_to_csv(data, columns, filename='report.csv'):
    """
    Export data to CSV format.
    
    Args:
        data: List of dictionaries or QuerySet
        columns: List of column names
        filename: Output filename
    
    Returns:
        StringIO: CSV file content
    """
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    
    for row in data:
        writer.writerow(row)
    
    output.seek(0)
    return output


def format_currency(amount):
    """
    Format number as currency.
    
    Args:
        amount: Numeric amount
    
    Returns:
        str: Formatted currency string
    """
    if amount is None:
        return "$0.00"
    return f"${amount:,.2f}"


def format_percentage(value):
    """
    Format number as percentage.
    
    Args:
        value: Numeric value
    
    Returns:
        str: Formatted percentage string
    """
    if value is None:
        return "0.0%"
    return f"{value:.1f}%"


def get_comparison_data(transactions, current_start, current_end):
    """
    Get comparison data between current and previous periods.
    
    Args:
        transactions: QuerySet of Transaction objects
        current_start: Start of current period
        current_end: End of current period
    
    Returns:
        dict: Comparison statistics
    """
    # Calculate previous period dates
    period_length = (current_end - current_start).days
    previous_start = current_start - timedelta(days=period_length)
    previous_end = current_start
    
    # Current period stats
    current_transactions = transactions.filter(
        transaction_date__gte=current_start,
        transaction_date__lte=current_end,
        status='completed'
    )
    current_stats = calculate_revenue_stats(current_transactions)
    
    # Previous period stats
    previous_transactions = transactions.filter(
        transaction_date__gte=previous_start,
        transaction_date__lte=previous_end,
        status='completed'
    )
    previous_stats = calculate_revenue_stats(previous_transactions)
    
    # Calculate growth rates
    revenue_growth = calculate_growth_rate(
        current_stats['total_revenue'],
        previous_stats['total_revenue']
    )
    
    transaction_growth = calculate_growth_rate(
        current_stats['total_transactions'],
        previous_stats['total_transactions']
    )
    
    return {
        'current': current_stats,
        'previous': previous_stats,
        'revenue_growth': revenue_growth,
        'transaction_growth': transaction_growth,
    }


def calculate_retention_rate(tenant_customers, days=30):
    """
    Calculate customer retention rate.
    
    Args:
        tenant_customers: QuerySet of TenantCustomer objects
        days: Number of days to look back
    
    Returns:
        float: Retention rate percentage
    """
    cutoff_date = timezone.now() - timedelta(days=days)
    
    # Customers who joined before cutoff
    old_customers = tenant_customers.filter(
        joined_at__lt=cutoff_date,
        role='customer'
    ).count()
    
    # Of those, how many made a purchase recently
    if old_customers > 0:
        retained = tenant_customers.filter(
            joined_at__lt=cutoff_date,
            last_purchase_at__gte=cutoff_date,
            role='customer'
        ).count()
        
        retention_rate = (retained / old_customers) * 100
    else:
        retention_rate = 0
    
    return round(retention_rate, 2)
