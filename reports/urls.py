"""
Reports App URL Configuration
"""
from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    # Command Center (Main Dashboard)
    path('', views.reports_dashboard, name='dashboard'),
    
    # Platform Dashboards
    path('platform/', views.platform_dashboard, name='platform_dashboard'),
    path('platform-revenue/', views.platform_revenue_dashboard, name='platform_revenue'),
    
    # Detailed reports
    path('revenue/', views.revenue_report, name='revenue'),
    path('customers/', views.customer_report, name='customers'),
    path('sales/', views.sales_report, name='sales'),
    path('loyalty/', views.loyalty_report, name='loyalty'),
    path('rental/', views.rental_report, name='rental_report'),
    
    # Export functionality
    path('export/revenue/', views.export_revenue_csv, name='export_revenue'),
    path('export/customers/', views.export_customers_csv, name='export_customers'),
    path('export/rentals/', views.export_rentals, name='export_rentals'),
    
    # Print reports
    path('print/<str:report_type>/', views.print_report, name='print_report'),
]