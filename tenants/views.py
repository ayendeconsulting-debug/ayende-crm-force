"""
Dashboard URL Configuration
Tenant-aware URL patterns for customer and business interfaces
"""

from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # Public tenant pages (no login required)
    path('register/', views.customer_register, name='register'),
    path('login/', views.customer_login_view, name='login'),
    
    # Customer dashboard (login required)
    path('dashboard/', views.dashboard_home, name='home'),
    path('logout/', views.customer_logout_view, name='logout'),
    
    # Business customer management (staff only)
    path('customers/', views.manage_customers, name='manage_customers'),
    path('customers/<int:customer_id>/', views.customer_detail, name='customer_detail'),
    path('customers/add/', views.add_customer, name='add_customer'),
    path('customers/<int:customer_id>/edit/', views.edit_customer, name='edit_customer'),
    path('customers/<int:customer_id>/delete/', views.delete_customer, name='delete_customer'),
    path('customers/<int:customer_id>/notes/', views.edit_customer_notes, name='edit_customer_notes'),
]