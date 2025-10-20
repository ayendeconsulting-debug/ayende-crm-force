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
    
    # Dashboard
    path('', views.dashboard_home, name='home'),
    
    # Password Reset URLs
    path('password-reset/', 
         auth_views.PasswordResetView.as_view(
             template_name='dashboard/password_reset.html',
             email_template_name='dashboard/password_reset_email.txt',
             subject_template_name='dashboard/password_reset_subject.txt',
             success_url='/password-reset/done/'
         ), 
         name='password_reset'),
    
    path('password-reset/done/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='dashboard/password_reset_done.html'
         ), 
         name='password_reset_done'),
    
    path('reset/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
             template_name='dashboard/password_reset_confirm.html',
             success_url='/reset/done/'
         ), 
         name='password_reset_confirm'),
    
    path('reset/done/', 
         auth_views.PasswordResetCompleteView.as_view(
             template_name='dashboard/password_reset_complete.html'
         ), 
         name='password_reset_complete'),
    
    # Business Owner Views
    path('customers/', views.manage_customers, name='manage_customers'),
    path('customers/add/', views.add_customer, name='add_customer'),
    path('customers/<int:customer_id>/', views.customer_detail, name='customer_detail'),
    path('customers/<int:customer_id>/edit/', views.edit_customer, name='edit_customer'),
    path('customers/<int:customer_id>/delete/', views.delete_customer, name='delete_customer'),
    path('customers/<int:customer_id>/notes/', views.edit_customer_notes, name='edit_customer_notes'),
]