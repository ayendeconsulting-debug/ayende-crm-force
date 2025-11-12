"""
Notification URLs for Ayende CX
Enhanced URL routing with campaigns + two-way messaging
"""

from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    # ==============================================
    # CAMPAIGNS (Your existing notification broadcasts)
    # ==============================================
    path('campaigns/compose/', views.compose_notification, name='compose'),
    path('campaigns/', views.notification_list, name='notification_list'),
    path('campaigns/<uuid:notification_id>/', views.notification_detail, name='notification_detail'),
    path('campaigns/<uuid:notification_id>/resend/', views.resend_notification, name='resend_notification'),

    # ==============================================
    # MESSAGES (New two-way messaging)
    # ==============================================
    path('messages/', views.staff_inbox, name='staff_inbox'),
    path('messages/<uuid:message_id>/', views.staff_message_detail, name='staff_message_detail'),
    path('messages/<uuid:message_id>/reply/', views.reply_to_message, name='reply_to_message'),
    
    # Message Composition
    path('compose/', views.compose_message, name='compose_message'),
    
    # Message Templates
    path('templates/', views.template_library, name='template_library'),
    path('templates/create/', views.create_template, name='create_template'),

    # ==============================================
    # CUSTOMER INBOX (Existing)
    # ==============================================
    path('inbox/', views.customer_inbox, name='inbox'),
    path('inbox/<uuid:recipient_id>/', views.view_notification, name='view_notification'),

    # ==============================================
    # AJAX ENDPOINTS
    # ==============================================
    # Existing endpoints
    path('api/mark-read/<uuid:recipient_id>/', views.mark_notification_read, name='mark_read'),
    path('api/mark-unread/<uuid:recipient_id>/', views.mark_notification_unread, name='mark_unread'),
    path('api/unread-count/', views.get_unread_count, name='unread_count'),
    
    # New endpoints
    path('api/template/<uuid:template_id>/', views.get_template_content, name='get_template'),
    path('api/archive/<uuid:message_id>/', views.archive_message, name='archive_message'),
]