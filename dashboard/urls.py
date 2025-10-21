"""
Dashboard URLs Configuration
Includes password reset functionality
"""

from django.urls import path
from django.contrib.auth import views as auth_views
from . import views


app_name = 'dashboard'

urlpatterns = [
    # Authentication
    path('register/', views.customer_register, name='register'),
    path('login/', views.customer_login_view, name='login'),
    path('logout/', views.customer_logout_view, name='logout'),
    
    # Dashboard - FIXED: Now at /dashboard/ instead of root
    path('dashboard/', views.dashboard_home, name='home'),
    
   # Password Reset Flow (ADD THESE)
    path('password-reset/', 
         views.TenantPasswordResetView.as_view(), 
         name='password_reset'),
    path('password-reset/done/', 
         views.TenantPasswordResetDoneView.as_view(), 
         name='password_reset_done'),
    path('password-reset/confirm/<uidb64>/<token>/', 
         views.TenantPasswordResetConfirmView.as_view(), 
         name='password_reset_confirm'),
    path('password-reset/complete/', 
         views.TenantPasswordResetCompleteView.as_view(), 
         name='password_reset_complete'),
    
    # Transactions (ADD THESE)
    path('transactions/', views.transaction_list, name='transaction_list'),
    path('transactions/<str:transaction_id>/', views.transaction_detail, name='transaction_detail'),
    
    # Business Owner Views
    path('customers/', views.manage_customers, name='manage_customers'),
    path('customers/add/', views.add_customer, name='add_customer'),
    path('customers/<int:customer_id>/', views.customer_detail, name='customer_detail'),
    path('customers/<int:customer_id>/edit/', views.edit_customer, name='edit_customer'),
    path('customers/<int:customer_id>/delete/', views.delete_customer, name='delete_customer'),
    path('customers/<int:customer_id>/notes/', views.edit_customer_notes, name='edit_customer_notes'),
]