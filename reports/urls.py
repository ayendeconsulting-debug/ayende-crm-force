"""
Reports App URL Configuration
"""

from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    # Main dashboard
    path('', views.reports_dashboard, name='dashboard'),
    
    # Detailed reports
    path('revenue/', views.revenue_report, name='revenue'),
    path('customers/', views.customer_report, name='customers'),
    path('sales/', views.sales_report, name='sales'),
    path('loyalty/', views.loyalty_report, name='loyalty'),
    
    # Export functionality
    path('export/revenue/', views.export_revenue_csv, name='export_revenue'),
    path('export/customers/', views.export_customers_csv, name='export_customers'),
    
    # Print reports
    path('print/<str:report_type>/', views.print_report, name='print_report'),
]
