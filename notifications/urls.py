"""
Notification URLs for Ayende CX
Fixed URL routing - removed duplicate/broken routes
"""
from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    # ==============================================
    # CAMPAIGNS (Notification broadcasts with segmentation)
    # ==============================================
    path('campaigns/compose/', views.compose_notification, name='compose'),
    path('campaigns/', views.notification_list, name='notification_list'),
    path('campaigns/<uuid:notification_id>/', views.notification_detail, name='notification_detail'),
    path('campaigns/<uuid:notification_id>/resend/', views.resend_notification, name='resend_notification'),
    
    # ==============================================
    # STAFF MESSAGES (Two-way messaging inbox)
    # ==============================================
    path('messages/', views.staff_inbox, name='staff_inbox'),
    path('messages/<uuid:message_id>/', views.staff_message_detail, name='staff_message_detail'),
    path('messages/<uuid:message_id>/reply/', views.reply_to_message, name='reply_to_message'),
    
    # ==============================================
    # CUSTOMER INBOX (Customer view of notifications)
    # ==============================================
    path('inbox/', views.customer_inbox, name='inbox'),
    path('inbox/<uuid:recipient_id>/', views.view_notification, name='view_notification'),
    
    # ==============================================
    # AJAX ENDPOINTS
    # ==============================================
    path('api/mark-read/<uuid:recipient_id>/', views.mark_notification_read, name='mark_read'),
    path('api/mark-unread/<uuid:recipient_id>/', views.mark_notification_unread, name='mark_unread'),
    path('api/unread-count/', views.get_unread_count, name='unread_count'),
    path('api/template/<uuid:template_id>/', views.get_template_content, name='get_template'),
    path('api/archive/<uuid:message_id>/', views.archive_message, name='archive_message'),
]

# ==============================================
# REMOVED BROKEN ROUTES:
# ==============================================
# path('compose/', views.compose_message, name='compose_message'),  
#   - Removed: Template doesn't exist
#   - Use: /campaigns/compose/ instead (has full segmentation)
#
# path('templates/', views.template_library, name='template_library'),
#   - Removed: Template doesn't exist  
#   - Message templates handled differently
# 
# path('templates/create/', views.create_template, name='create_template'),
#   - Removed: Template doesn't exist
# ==============================================