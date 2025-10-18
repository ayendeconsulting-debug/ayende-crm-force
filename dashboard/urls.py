from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # Authentication
    path('login/', views.customer_login_view, name='login'),
    path('register/', views.customer_register, name='register'),
    path('logout/', views.customer_logout_view, name='logout'),
    
    # Dashboard
    path('', views.dashboard_home, name='home'),
    path('profile/', views.customer_profile, name='profile'),
    
    # Transactions (Customer)
    path('transactions/', views.transaction_history, name='transactions'),
    path('transactions/<uuid:transaction_id>/', views.transaction_detail, name='transaction_detail'),
    
    # Customer Management (Business Owner)
    path('customers/', views.manage_customers, name='manage_customers'),
    path('customers/add/', views.add_customer, name='add_customer'),
    
    # CRITICAL FIX: Changed from <int:customer_id> to <uuid:customer_id>
    # Because TenantCustomer uses UUID as primary key
    path('customers/<uuid:customer_id>/', views.customer_detail_view, name='customer_detail'),
    path('customers/<uuid:customer_id>/edit/', views.edit_customer, name='edit_customer'),
    path('customers/<uuid:customer_id>/delete/', views.delete_customer, name='delete_customer'),
    path('customers/<uuid:customer_id>/notes/', views.edit_customer_notes, name='edit_customer_notes'),
]