"""
Dashboard URLs Configuration
Includes password reset functionality and integration endpoints
"""

from django.urls import path
from django.contrib.auth import views as auth_views

# Import regular views from dashboard.views (the views.py file)
from dashboard import views
from .views.main import check_customer_by_phone

# Import integration views from dashboard.views package (the views/ directory)
from dashboard.views import integration as integration_views
from dashboard.views import sync_views

app_name = 'dashboard'

urlpatterns = [
    # Authentication
    path('register/', views.main.customer_register, name='register'),
    path('login/', views.main.customer_login_view, name='login'),
    path('logout/', views.main.customer_logout_view, name='logout'),
    path('verify-email/<str:token>/', views.main.verify_email, name='verify_email'),
    path('resend-verification/', views.main.resend_verification_email, name='resend_verification'),
    path('api/debug/tenants', views.main.get_tenant_info, name='debug_tenants'),
    
    # Dashboard - Business Command Center (accessible at root, /dashboard/, and /admin/)
    path('', views.main.dashboard_home, name='home'),  # Root of subdomain
    path('dashboard/', views.main.dashboard_home, name='dashboard'),  # Also at /dashboard/
    path('admin/', views.main.dashboard_home, name='admin'),  # Also at /admin/ for business users
    # Customer Dashboard Enhancements
    path('customer/theme/toggle/', views.main.toggle_theme, name='toggle_theme'),
    
    # Customer Notifications
    path('customer/notifications/', views.main.customer_notifications, name='customer_notifications'),
    path('customer/notifications/<uuid:notification_id>/', views.main.customer_notification_detail, name='customer_notification_detail'),
    
    # Customer Messages
    path('customer/messages/', views.main.customer_messages, name='customer_messages'),
    path('customer/messages/<uuid:message_id>/', views.main.customer_message_detail, name='customer_message_detail'),
    path('customer/messages/compose/', views.main.compose_message_business, name='compose_message_business'),
    
    # Password Reset Flow
    path('password-reset/', 
         views.main.TenantPasswordResetView.as_view(), 
         name='password_reset'),
    path('password-reset/done/', 
         views.main.TenantPasswordResetDoneView.as_view(), 
         name='password_reset_done'),
    path('password-reset/confirm/<uidb64>/<token>/', 
         views.main.TenantPasswordResetConfirmView.as_view(), 
         name='password_reset_confirm'),
    path('password-reset/complete/', 
         views.main.TenantPasswordResetCompleteView.as_view(), 
         name='password_reset_complete'),
    
    # Transactions
    path('transactions/', views.main.transaction_list, name='transaction_list'),
    path('transactions/<str:transaction_id>/', views.main.transaction_detail, name='transaction_detail'),
    
    # Business Owner Views
    path('customers/', views.main.manage_customers, name='manage_customers'),
    path('customers/add/', views.main.add_customer, name='add_customer'),
    path('customers/<uuid:customer_id>/', views.main.customer_detail, name='customer_detail'),
    path('customers/<uuid:customer_id>/edit/', views.main.edit_customer, name='edit_customer'),
    path('customers/<uuid:customer_id>/delete/', views.main.delete_customer, name='delete_customer'),
    path('customers/<uuid:customer_id>/notes/', views.main.edit_customer_notes, name='edit_customer_notes'),
    path('api/v1/customers/check-phone', check_customer_by_phone, name='check-customer-phone'),
    path('api/sync/customers', sync_views.get_updated_customers, name='sync_customers'),
    path('customers/export/', views.main.export_customers, name='export_customers'),
    # Rental Contracts
    path('rentals/', views.main.rental_list, name='rentals'),
    path('rentals/<uuid:rental_id>/', views.main.rental_detail, name='rental_detail'),
  
    # ============================================
    # INTEGRATION: Sync endpoints from POS
    # ============================================
    path('api/sync/health/', 
         integration_views.SyncHealthView.as_view(), 
         name='sync_health'),
    
    path('api/sync/transaction/', 
         integration_views.TransactionSyncView.as_view(), 
         name='sync_transaction'),
    
    path('api/sync/customer/', 
         integration_views.CustomerSyncView.as_view(), 
         name='sync_customer'),
    
   path('api/sync/customer-batch/', 
         integration_views.CustomerBatchSyncView.as_view(), 
         name='sync_customer_batch'),
    
    # Rental sync from POS
    path('api/v1/sync/rental',
         sync_views.receive_rental,
         name='sync_rental'),
    
    
]
