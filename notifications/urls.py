"""
Notification URLs for Ayende CX
URL routing for notification system

UPDATED: Added staff_inbox URL pattern to fix NoReverseMatch error
FIXED: Added missing compose_message and template_library URLs
"""

from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    # Business Owner URLs (Sending Notifications/Campaigns)
    path('compose/', views.compose_notification, name='compose'),
    path('', views.notification_list, name='notification_list'),
    path('<uuid:notification_id>/', views.notification_detail, name='notification_detail'),
    path('<uuid:notification_id>/resend/', views.resend_notification, name='resend_notification'),
    
    # Staff/Business Messaging URLs
    path('staff/inbox/', views.staff_inbox, name='staff_inbox'),
    path('messages/compose/', views.compose_message, name='compose_message'),  # ADD THIS
    path('templates/', views.template_library, name='template_library'),        # ADD THIS
    path('templates/create/', views.create_template, name='create_template'),
    
    # Customer URLs (Receiving Notifications)
    path('inbox/', views.customer_inbox, name='inbox'),
    path('inbox/<uuid:recipient_id>/', views.view_notification, name='view_notification'),
    
    # AJAX Endpoints
    path('api/mark-read/<uuid:recipient_id>/', views.mark_notification_read, name='mark_read'),
    path('api/mark-unread/<uuid:recipient_id>/', views.mark_notification_unread, name='mark_unread'),
    path('api/unread-count/', views.get_unread_count, name='unread_count'),
]