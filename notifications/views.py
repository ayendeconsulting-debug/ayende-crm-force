"""
Notification Views for Ayende CX
Views for creating, managing, and viewing notifications
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from customers.models import Transaction
from django.contrib import messages as django_messages

from .models import Notification, NotificationRecipient
from .forms import NotificationComposeForm
from .models import Message, MessageTemplate
from customers.models import TenantCustomer


# Business Owner Views (Sending Notifications)

@login_required
def compose_notification(request):
    """
    Business owner view to compose and send notifications.
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to compose notification.')
        return redirect('dashboard:home')
    
    # Verify permissions
    try:
        tenant_customer = request.user
        
        if not tenant_customer.is_staff_member:
            messages.error(request, 'You do not have permission to send notifications.')
            return redirect('dashboard:home')
            
    except TenantCustomer.DoesNotExist:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:login')
    
    if request.method == 'POST':
        form = NotificationComposeForm(request.POST, tenant=tenant)
        if form.is_valid():
            notification = form.save(commit=False)
            notification.created_by = request.user
            notification.save()
            
            # If specific customers selected, save the many-to-many
            target_audience = form.cleaned_data.get('target_audience')
            if target_audience == 'specific':
                form.save_m2m()
            
            # Send notification immediately if not scheduled
            send_option = form.cleaned_data.get('send_option')
            if send_option == 'now':
                success = notification.send_notification()
                if success:
                    messages.success(
                        request,
                        f'Notification "{notification.title}" has been sent to {notification.total_delivered} customer(s).'
                    )
                else:
                    messages.error(
                        request,
                        'Failed to send notification. No eligible customers found.'
                    )
            else:
                messages.success(
                    request,
                    f'Notification "{notification.title}" has been scheduled for {notification.scheduled_for.strftime("%B %d, %Y at %I:%M %p")}.'
                )
            
            return redirect('notifications:notification_list')
    else:
        form = NotificationComposeForm(tenant=tenant)
    
    # Get recipient count preview for different targeting options
    all_customers_count = TenantCustomer.objects.filter(
        tenant=tenant,
        role='customer',
        is_active=True
    ).count()
    
    vip_customers_count = TenantCustomer.objects.filter(
        tenant=tenant,
        role='customer',
        is_active=True,
        is_vip=True
    ).count()
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'is_business_view': True,
        'form': form,
        'all_customers_count': all_customers_count,
        'vip_customers_count': vip_customers_count,
    }
    
    return render(request, 'notifications/compose.html', context)


@login_required
def notification_list(request):
    """
    Business owner view to see all sent notifications.
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to load notifications.')
        return redirect('dashboard:home')
    
    # Verify permissions
    try:
        tenant_customer = request.user
        
        if not tenant_customer.is_staff_member:
            messages.error(request, 'You do not have permission to view notifications.')
            return redirect('dashboard:home')
            
    except TenantCustomer.DoesNotExist:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:login')
    
    # Get all notifications for this tenant
    notifications = Notification.objects.filter(
        tenant=tenant
    ).order_by('-created_at')
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter:
        notifications = notifications.filter(status=status_filter)
    
    # Filter by category
    category_filter = request.GET.get('category', '')
    if category_filter:
        notifications = notifications.filter(category=category_filter)
    
    # Search
    search_query = request.GET.get('search', '')
    if search_query:
        notifications = notifications.filter(
            Q(title__icontains=search_query) |
            Q(message__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(notifications, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    total_sent = Notification.objects.filter(
        tenant=tenant,
        status='sent'
    ).count()
    
    total_scheduled = Notification.objects.filter(
        tenant=tenant,
        status='scheduled'
    ).count()
    
    total_recipients = Notification.objects.filter(
        tenant=tenant,
        status='sent'
    ).aggregate(total=Count('recipients'))['total'] or 0
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'is_business_view': True,
        'notifications': page_obj,
        'status_filter': status_filter,
        'category_filter': category_filter,
        'search_query': search_query,
        'total_sent': total_sent,
        'total_scheduled': total_scheduled,
        'total_recipients': total_recipients,
    }
    
    return render(request, 'notifications/list.html', context)


@login_required
def notification_detail(request, notification_id):
    """
    Business owner view to see detailed notification statistics.
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to load notification.')
        return redirect('dashboard:home')
    
    # Verify permissions
    try:
        tenant_customer = request.user
        
        if not tenant_customer.is_staff_member:
            messages.error(request, 'You do not have permission to view this notification.')
            return redirect('dashboard:home')
            
    except TenantCustomer.DoesNotExist:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:login')
    
    # Get notification
    notification = get_object_or_404(
        Notification,
        id=notification_id,
        tenant=tenant
    )
    
    # Get recipients with pagination
    recipients = NotificationRecipient.objects.filter(
        notification=notification
    ).select_related('tenant_customer__customer').order_by('-created_at')
    
    # Filter recipients by read status
    read_filter = request.GET.get('read_status', '')
    if read_filter == 'read':
        recipients = recipients.filter(is_read=True)
    elif read_filter == 'unread':
        recipients = recipients.filter(is_read=False)
    
    # Pagination
    paginator = Paginator(recipients, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'is_business_view': True,
        'notification': notification,
        'recipients': page_obj,
        'read_filter': read_filter,
    }
    
    return render(request, 'notifications/detail.html', context)


@login_required
def resend_notification(request, notification_id):
    """
    Resend a notification to customers who didn't receive it.
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to resend notification.')
        return redirect('dashboard:home')
    
    # Verify permissions
    try:
        tenant_customer = request.user
        
        if not tenant_customer.is_staff_member:
            messages.error(request, 'You do not have permission to resend notifications.')
            return redirect('dashboard:home')
            
    except TenantCustomer.DoesNotExist:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:login')
    
    # Get notification
    notification = get_object_or_404(
        Notification,
        id=notification_id,
        tenant=tenant
    )
    
    if request.method == 'POST':
        # Resend notification
        success = notification.send_notification()
        if success:
            messages.success(
                request,
                f'Notification "{notification.title}" has been resent successfully.'
            )
        else:
            messages.error(request, 'Failed to resend notification.')
        
        return redirect('notifications:notification_detail', notification_id=notification.id)
    
    return redirect('notifications:notification_detail', notification_id=notification.id)


# Customer Views (Receiving Notifications)

@login_required
def customer_inbox(request):
    """
    Customer view to see their notifications (inbox).
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to load inbox.')
        return redirect('dashboard:home')
    
    # Get customer-tenant relationship
    try:
        tenant_customer = request.user
        
    except TenantCustomer.DoesNotExist:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:login')
    
    # Get all notifications for this customer
    notifications = NotificationRecipient.objects.filter(
        tenant_customer=tenant_customer
    ).select_related('notification').order_by('-created_at')
    
    # Filter by read status
    status_filter = request.GET.get('status', '')
    if status_filter == 'unread':
        notifications = notifications.filter(is_read=False)
    elif status_filter == 'read':
        notifications = notifications.filter(is_read=True)
    
    # Filter by category
    category_filter = request.GET.get('category', '')
    if category_filter:
        notifications = notifications.filter(notification__category=category_filter)
    
    # Pagination
    paginator = Paginator(notifications, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get unread count
    unread_count = NotificationRecipient.objects.filter(
        tenant_customer=tenant_customer,
        is_read=False
    ).count()
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'notifications': page_obj,
        'unread_count': unread_count,
        'status_filter': status_filter,
        'category_filter': category_filter,
    }
    
    return render(request, 'notifications/inbox.html', context)


@login_required
def view_notification(request, recipient_id):
    """
    Customer view to read a specific notification.
    Automatically marks as read.
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to view notification.')
        return redirect('dashboard:home')
    
    # Get customer-tenant relationship
    try:
        tenant_customer = request.user
        
    except TenantCustomer.DoesNotExist:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:login')
    
    # Get notification recipient
    recipient = get_object_or_404(
        NotificationRecipient,
        id=recipient_id,
        tenant_customer=tenant_customer
    )
    
    # Mark as read
    recipient.mark_as_read()
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'recipient': recipient,
        'notification': recipient.notification,
    }
    
    return render(request, 'notifications/view.html', context)


@login_required
def mark_notification_read(request, recipient_id):
    """
    AJAX endpoint to mark notification as read.
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        return JsonResponse({'success': False, 'error': 'Invalid tenant'})
    
    # Get customer-tenant relationship
    try:
        tenant_customer = request.user
        
    except TenantCustomer.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Access denied'})
    
    # Get notification recipient
    try:
        recipient = NotificationRecipient.objects.get(
            id=recipient_id,
            tenant_customer=tenant_customer
        )
    except NotificationRecipient.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Notification not found'})
    
    # Mark as read
    success = recipient.mark_as_read()
    
    # Get updated unread count
    unread_count = NotificationRecipient.objects.filter(
        tenant_customer=tenant_customer,
        is_read=False
    ).count()
    
    return JsonResponse({
        'success': success,
        'unread_count': unread_count
    })


@login_required
def mark_notification_unread(request, recipient_id):
    """
    AJAX endpoint to mark notification as unread.
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        return JsonResponse({'success': False, 'error': 'Invalid tenant'})
    
    # Get customer-tenant relationship
    try:
        tenant_customer = request.user
        
    except TenantCustomer.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Access denied'})
    
    # Get notification recipient
    try:
        recipient = NotificationRecipient.objects.get(
            id=recipient_id,
            tenant_customer=tenant_customer
        )
    except NotificationRecipient.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Notification not found'})
    
    # Mark as unread
    success = recipient.mark_as_unread()
    
    # Get updated unread count
    unread_count = NotificationRecipient.objects.filter(
        tenant_customer=tenant_customer,
        is_read=False
    ).count()
    
    return JsonResponse({
        'success': success,
        'unread_count': unread_count
    })


@login_required
def get_unread_count(request):
    """
    AJAX endpoint to get unread notification count.
    Used for badge updates.
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        return JsonResponse({'success': False, 'error': 'Invalid tenant'})
    
    # Get customer-tenant relationship
    try:
        tenant_customer = request.user
        
    except TenantCustomer.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Access denied'})
    
    # Get unread count
    unread_count = NotificationRecipient.objects.filter(
        tenant_customer=tenant_customer,
        is_read=False
    ).count()
    
    return JsonResponse({
        'success': True,
        'unread_count': unread_count
    })
    
    # ============================================
   # ENHANCED COMMUNICATION VIEWS
   # Staff inbox, messaging, templates
   # ============================================
   
@login_required
def staff_inbox(request):
    """
    Staff inbox to view messages from customers.
    Shows customer_to_business messages.
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        django_messages.error(request, 'Unable to load inbox.')
        return redirect('dashboard:home')
    
    # Verify permissions - only staff can access
    tenant_customer = request.user
    if not tenant_customer.is_staff_member:
        django_messages.error(request, 'You do not have permission to access staff inbox.')
        return redirect('dashboard:home')
    
    # Get all customer messages to this business
    messages_list = Message.objects.filter(
        tenant=tenant,
        message_type='customer_to_business'
    ).select_related('sender').order_by('-created_at')
    # UPDATED STAFF_INBOX VIEW SECTION
# Replace lines 537-597 in notifications/views.py

    # Filter by status (updated parameter name from 'status' to 'filter')
    filter_param = request.GET.get('filter', 'all')
    if filter_param == 'unread':
        messages_list = messages_list.filter(status__in=['sent', 'delivered'])
    elif filter_param == 'read':
        messages_list = messages_list.filter(status='read')
    elif filter_param == 'archived':
        messages_list = messages_list.filter(status='archived')
    elif filter_param == 'urgent':
        messages_list = messages_list.filter(priority='urgent')
    elif filter_param == 'high':
        messages_list = messages_list.filter(priority='high')

    # Search
    search_query = request.GET.get('search', '')
    if search_query:
        messages_list = messages_list.filter(
            Q(subject__icontains=search_query) |
            Q(body__icontains=search_query) |
            Q(sender__first_name__icontains=search_query) |
            Q(sender__last_name__icontains=search_query)
        )

    # Pagination
    paginator = Paginator(messages_list, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    from datetime import date
    
    unread_count = Message.objects.filter(
        tenant=tenant,
        message_type='customer_to_business',
        status__in=['sent', 'delivered']
    ).count()
    
    total_messages = Message.objects.filter(
        tenant=tenant,
        message_type='customer_to_business'
    ).count()
    
    urgent_count = Message.objects.filter(
        tenant=tenant,
        message_type='customer_to_business',
        priority='urgent',
        status__in=['sent', 'delivered']
    ).count()
    
    today_count = Message.objects.filter(
        tenant=tenant,
        message_type='customer_to_business',
        created_at__date=date.today()
    ).count()
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'is_business_view': True,
        'messages': page_obj,
        'unread_count': unread_count,
        'total_messages': total_messages,
        'urgent_count': urgent_count,
        'today_count': today_count,
        'filter': filter_param,
        'search_query': search_query,
    }
    
    return render(request, 'notifications/staff_inbox.html', context)


@login_required
def staff_message_detail(request, message_id):
    """
    Staff view a specific message from customer.
    Shows full conversation thread.
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        django_messages.error(request, 'Unable to load message.')
        return redirect('dashboard:home')
    
    tenant_customer = request.user
    if not tenant_customer.is_staff_member:
        django_messages.error(request, 'Access denied.')
        return redirect('dashboard:home')
    
    # Get message
    message = get_object_or_404(
        Message,
        id=message_id,
        tenant=tenant
    )
    
    # Mark as read if unread
    if message.is_unread:
        message.mark_as_read()
    
    # Get conversation thread
    conversation = message.get_conversation_thread()
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'is_business_view': True,
        'message': message,
        'conversation': conversation,
    }
    
    return render(request, 'notifications/staff_message_detail.html', context)


# ==============================================
# MESSAGE COMPOSITION VIEWS (Staff Send Messages)
# ==============================================

@login_required
def compose_message(request):
    """
    Staff compose message to send to customer.
    Can use templates.
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        django_messages.error(request, 'Unable to compose message.')
        return redirect('dashboard:home')
    
    tenant_customer = request.user
    if not tenant_customer.is_staff_member:
        django_messages.error(request, 'Access denied.')
        return redirect('dashboard:home')
    
    if request.method == 'POST':
        receiver_id = request.POST.get('receiver')
        subject = request.POST.get('subject')
        body = request.POST.get('body')
        priority = request.POST.get('priority', 'normal')
        template_id = request.POST.get('template')
        
        # Validate
        if not receiver_id or not subject or not body:
            django_messages.error(request, 'Please fill in all required fields.')
            return redirect('notifications:compose_message')
        
        try:
            receiver = TenantCustomer.objects.get(
                id=receiver_id,
                tenant=tenant,
                role='customer'
            )
        except TenantCustomer.DoesNotExist:
            django_messages.error(request, 'Invalid recipient.')
            return redirect('notifications:compose_message')
        
        # ✅ FIX: Render template variables if template was used
        template_obj = None
        if template_id:
            try:
                template_obj = MessageTemplate.objects.get(id=template_id, tenant=tenant)
                # Render template with customer data (replaces {{first_name}}, {{business_name}}, etc.)
                subject, body = template_obj.render(receiver)
            except MessageTemplate.DoesNotExist:
                pass
        # If no template, use the subject/body from form as-is
        
        # Create message with rendered content
        message = Message.objects.create(
            tenant=tenant,
            sender=tenant_customer,
            receiver=receiver,
            message_type='business_to_customer',
            subject=subject,  # ✅ Now contains rendered content
            body=body,        # ✅ Now contains rendered content
            priority=priority,
            status='sent',
            sent_at=timezone.now()
        )
        
        # Link template and increment usage
        if template_obj:
            message.template_used = template_obj
            message.save()
            template_obj.increment_usage()
        
        django_messages.success(
            request,
            f'Message sent successfully to {receiver.first_name} {receiver.last_name}!'
        )
        return redirect('notifications:staff_inbox')
    
    # GET request - show form
    # Get all customers for this tenant
    customers = TenantCustomer.objects.filter(
        tenant=tenant,
        role='customer',
        is_active=True
    ).order_by('first_name', 'last_name')
    
    # Get active templates
    templates = MessageTemplate.objects.filter(
        tenant=tenant,
        is_active=True
    ).order_by('name')
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'is_business_view': True,
        'customers': customers,
        'templates': templates,
    }
    
    return render(request, 'notifications/compose_message.html', context)


@login_required
def reply_to_message(request, message_id):
    """
    Staff reply to a customer message.
    Creates threaded conversation.
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        return JsonResponse({'success': False, 'error': 'Invalid tenant'})
    
    tenant_customer = request.user
    if not tenant_customer.is_staff_member:
        return JsonResponse({'success': False, 'error': 'Access denied'})
    
    if request.method == 'POST':
        # Get original message
        try:
            original_message = Message.objects.get(
                id=message_id,
                tenant=tenant
            )
        except Message.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Message not found'})
        
        reply_body = request.POST.get('reply_body')
        if not reply_body:
            return JsonResponse({'success': False, 'error': 'Reply cannot be empty'})
        
        # Create reply message
        reply = Message.objects.create(
            tenant=tenant,
            sender=tenant_customer,
            receiver=original_message.sender,  # Reply to original sender
            message_type='business_to_customer',
            subject=f"Re: {original_message.subject}",
            body=reply_body,
            parent_message=original_message,  # Link to parent
            status='sent',
            sent_at=timezone.now()
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Reply sent successfully',
            'reply_id': str(reply.id)
        })
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


# ==============================================
# MESSAGE TEMPLATE VIEWS
# ==============================================

@login_required
def template_library(request):
    """
    Staff view and manage message templates.
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        django_messages.error(request, 'Unable to load templates.')
        return redirect('dashboard:home')
    
    tenant_customer = request.user
    if not tenant_customer.is_staff_member:
        django_messages.error(request, 'Access denied.')
        return redirect('dashboard:home')
    
    # Get all templates for this tenant
    templates = MessageTemplate.objects.filter(
        tenant=tenant
    ).order_by('-times_used', 'name')
    
    # Filter by type
    type_filter = request.GET.get('type', '')
    if type_filter:
        templates = templates.filter(template_type=type_filter)
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        templates = templates.filter(is_active=True)
    elif status_filter == 'inactive':
        templates = templates.filter(is_active=False)
    
    # Statistics
    total_templates = templates.count()
    most_used = templates.first() if templates.exists() else None
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'is_business_view': True,
        'templates': templates,
        'type_filter': type_filter,
        'status_filter': status_filter,
        'total_templates': total_templates,
        'most_used': most_used,
    }
    
    return render(request, 'notifications/template_library.html', context)


@login_required
def create_template(request):
    """
    Staff create new message template.
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        django_messages.error(request, 'Unable to create template.')
        return redirect('dashboard:home')
    
    tenant_customer = request.user
    if not tenant_customer.is_staff_member:
        django_messages.error(request, 'Access denied.')
        return redirect('dashboard:home')
    
    if request.method == 'POST':
        name = request.POST.get('name')
        template_type = request.POST.get('template_type')
        subject = request.POST.get('subject')
        body = request.POST.get('body')
        
        if not all([name, template_type, subject, body]):
            django_messages.error(request, 'Please fill in all required fields.')
            return redirect('notifications:create_template')
        
        # Create template
        template = MessageTemplate.objects.create(
            tenant=tenant,
            created_by=tenant_customer,
            name=name,
            template_type=template_type,
            subject=subject,
            body=body,
            is_active=True
        )
        
        django_messages.success(request, f'Template "{name}" created successfully!')
        return redirect('notifications:template_library')
    
    # GET - show form
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'is_business_view': True,
        'available_variables': [
            '{{customer_name}}',
            '{{first_name}}',
            '{{last_name}}',
            '{{email}}',
            '{{phone}}',
            '{{points}}',
            '{{business_name}}',
        ]
    }
    
    return render(request, 'notifications/create_template.html', context)


# ==============================================
# AJAX API ENDPOINTS
# ==============================================

@login_required
def get_template_content(request, template_id):
    """
    AJAX: Get template content for preview/use.
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        return JsonResponse({'success': False, 'error': 'Invalid tenant'})
    
    try:
        template = MessageTemplate.objects.get(
            id=template_id,
            tenant=tenant
        )
        
        return JsonResponse({
            'success': True,
            'subject': template.subject,
            'body': template.body,
            'variables': template.available_variables
        })
    except MessageTemplate.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Template not found'})


@login_required
def archive_message(request, message_id):
    """
    AJAX: Archive a message.
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        return JsonResponse({'success': False, 'error': 'Invalid tenant'})
    
    tenant_customer = request.user
    if not tenant_customer.is_staff_member:
        return JsonResponse({'success': False, 'error': 'Access denied'})
    
    try:
        message = Message.objects.get(
            id=message_id,
            tenant=tenant
        )
        message.status = 'archived'
        message.save()
        
        return JsonResponse({'success': True})
    except Message.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Message not found'})
    
@login_required
def compose_broadcast_message(request):
    """
    Staff compose broadcast message to multiple customers with segmentation.
    Supports targeting by: all, VIP, points range, spending tier, purchase history
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to compose message.')
        return redirect('dashboard:home')
    
    tenant_customer = request.user
    if not tenant_customer.is_staff_member:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:home')
    
    if request.method == 'POST':
        subject = request.POST.get('subject')
        body = request.POST.get('body')
        priority = request.POST.get('priority', 'normal')
        template_id = request.POST.get('template')
        
        # Targeting options
        target_type = request.POST.get('target_type')
        points_min = request.POST.get('points_min')
        points_max = request.POST.get('points_max')
        spending_tier = request.POST.get('spending_tier')
        specific_customers = request.POST.getlist('specific_customers')
        
        # Validate
        if not subject or not body:
            messages.error(request, 'Please fill in subject and message.')
            return redirect('notifications:compose_broadcast')
        
        # Get target customers based on segmentation
        customers = TenantCustomer.objects.filter(
            tenant=tenant,
            role='customer',
            is_active=True
        )
        
        # Apply filters based on target type
        if target_type == 'vip':
            customers = customers.filter(is_vip=True)
        
        elif target_type == 'points_range':
            if points_min:
                customers = customers.filter(loyalty_points__gte=int(points_min))
            if points_max:
                customers = customers.filter(loyalty_points__lte=int(points_max))
        
        elif target_type == 'spending_tier':
    # Use existing total_spent field on model
            
            if spending_tier == 'low':
                customers = customers.filter(Q(total_spent__lte=100) | Q(total_spent__isnull=True))
            elif spending_tier == 'medium':
                customers = customers.filter(total_spent__gt=100, total_spent__lte=500)
            elif spending_tier == 'high':
                customers = customers.filter(total_spent__gt=500, total_spent__lte=1000)
            elif spending_tier == 'vip':
                customers = customers.filter(total_spent__gt=1000)

        elif target_type == 'inactive_3m':
            # Customers with no transactions in last 3 months
            three_months_ago = timezone.now() - timedelta(days=90)
            active_customer_ids = Transaction.objects.filter(
                tenant=tenant,
                tenant_customer__in=customers,
                transaction_date__gte=three_months_ago
            ).values_list('tenant_customer_id', flat=True).distinct()
            customers = customers.exclude(id__in=active_customer_ids)

        elif target_type == 'inactive_6m':
            # Customers with no transactions in last 6 months
            six_months_ago = timezone.now() - timedelta(days=180)
            active_customer_ids = Transaction.objects.filter(
                tenant=tenant,
                tenant_customer__in=customers,
                transaction_date__gte=six_months_ago
            ).values_list('tenant_customer_id', flat=True).distinct()
            customers = customers.exclude(id__in=active_customer_ids)

        elif target_type == 'specific':
            if specific_customers:
                customers = customers.filter(id__in=specific_customers)
            else:
                messages.error(request, 'Please select at least one customer.')
                return redirect('notifications:compose_broadcast')
        
        recipient_count = customers.count()
        
        if recipient_count == 0:
            messages.error(request, 'No customers match the selected criteria.')
            return redirect('notifications:compose_broadcast')
        
        # Get template if used
        template_obj = None
        if template_id:
            try:
                template_obj = MessageTemplate.objects.get(id=template_id, tenant=tenant)
            except MessageTemplate.DoesNotExist:
                pass
        
        # Send message to each customer
        messages_sent = 0
        for customer in customers:
            # Render template with customer data if template is used
            if template_obj:
                rendered_subject, rendered_body = template_obj.render(customer)
            else:
                rendered_subject = subject
                rendered_body = body
            
            # Create message
            Message.objects.create(
                tenant=tenant,
                sender=tenant_customer,
                receiver=customer,
                message_type='business_to_customer',
                subject=rendered_subject,
                body=rendered_body,
                priority=priority,
                status='sent',
                sent_at=timezone.now(),
                template_used=template_obj
            )
            messages_sent += 1
        
        # Increment template usage
        if template_obj:
            template_obj.times_used += messages_sent
            template_obj.last_used_at = timezone.now()
            template_obj.save()
        
        messages.success(
            request,
            f'Broadcast message sent successfully to {messages_sent} customer(s)!'
        )
        return redirect('notifications:staff_inbox')
    
    # GET request - show form
    customers = TenantCustomer.objects.filter(
    tenant=tenant,
    role='customer',
    is_active=True
    ).order_by('first_name', 'last_name')
    
    # Get statistics for preview
    all_count = customers.count()
    vip_count = customers.filter(is_vip=True).count()
    
    # Spending tiers
    low_spenders = customers.filter(Q(total_spent__lte=100) | Q(total_spent__isnull=True)).count()
    medium_spenders = customers.filter(total_spent__gt=100, total_spent__lte=500).count()
    high_spenders = customers.filter(total_spent__gt=500, total_spent__lte=1000).count()
    vip_spenders = customers.filter(total_spent__gt=1000).count()

    # Inactive customer segments (based on last transaction date)
    now = timezone.now()
    three_months_ago = now - timedelta(days=90)
    six_months_ago = now - timedelta(days=180)
    
    # Get customer IDs who have transacted in last 3 months
    active_3m_ids = Transaction.objects.filter(
        tenant=tenant,
        tenant_customer__in=customers,
        transaction_date__gte=three_months_ago
    ).values_list('tenant_customer_id', flat=True).distinct()
    
    # Get customer IDs who have transacted in last 6 months
    active_6m_ids = Transaction.objects.filter(
        tenant=tenant,
        tenant_customer__in=customers,
        transaction_date__gte=six_months_ago
    ).values_list('tenant_customer_id', flat=True).distinct()
    
    # Inactive 3+ months: not in active_3m_ids
    inactive_3m_count = customers.exclude(id__in=active_3m_ids).count()
    
    # Inactive 6+ months: not in active_6m_ids
    inactive_6m_count = customers.exclude(id__in=active_6m_ids).count()

    # Get templates
    templates = MessageTemplate.objects.filter(
        tenant=tenant,
        is_active=True
    ).order_by('name')
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'is_business_view': True,
        'customers': customers,
        'templates': templates,
        'all_count': all_count,
        'vip_count': vip_count,
        'low_spenders': low_spenders,
        'medium_spenders': medium_spenders,
        'high_spenders': high_spenders,
        'vip_spenders': vip_spenders,
        'inactive_3m_count': inactive_3m_count,
        'inactive_6m_count': inactive_6m_count,
    }

    return render(request, 'notifications/compose_broadcast.html', context)

