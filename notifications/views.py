"""
Notification Views for Ayende CRMForce
Views for creating, managing, and viewing notifications
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.http import JsonResponse
from django.utils import timezone

from .models import Notification, NotificationRecipient
from .forms import NotificationComposeForm
from customers.models import TenantCustomer


# Business Owner Views (Sending Notifications)

@login_required(login_url='dashboard:login')
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
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
        
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


@login_required(login_url='dashboard:login')
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
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
        
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


@login_required(login_url='dashboard:login')
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
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
        
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


@login_required(login_url='dashboard:login')
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
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
        
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

@login_required(login_url='dashboard:login')
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
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
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


@login_required(login_url='dashboard:login')
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
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
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


@login_required(login_url='dashboard:login')
def mark_notification_read(request, recipient_id):
    """
    AJAX endpoint to mark notification as read.
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        return JsonResponse({'success': False, 'error': 'Invalid tenant'})
    
    # Get customer-tenant relationship
    try:
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
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


@login_required(login_url='dashboard:login')
def mark_notification_unread(request, recipient_id):
    """
    AJAX endpoint to mark notification as unread.
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        return JsonResponse({'success': False, 'error': 'Invalid tenant'})
    
    # Get customer-tenant relationship
    try:
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
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


@login_required(login_url='dashboard:login')
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
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
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
