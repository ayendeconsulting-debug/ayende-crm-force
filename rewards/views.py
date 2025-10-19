"""
Rewards Views for Ayende CX
Customer redemption catalog and business owner management
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.http import JsonResponse
from django.utils import timezone

from .models import Reward, Redemption, RewardCategory
from .forms import (
    RewardForm, 
    RedemptionForm, 
    RedemptionApprovalForm,
    RedemptionUseForm,
    RewardSearchForm
)
from customers.models import TenantCustomer


# =============================================================================
# CUSTOMER VIEWS - Rewards Catalog & Redemption
# =============================================================================

@login_required(login_url='dashboard:login')
def rewards_catalog(request):
    """
    Customer view: Browse available rewards and redeem
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to load rewards catalog.')
        return redirect('dashboard:home')
    
    # Get customer-tenant relationship
    try:
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
    except TenantCustomer.DoesNotExist:
        messages.error(request, 'You do not have access to this page.')
        return redirect('dashboard:login')
    
    # Get all active rewards
    rewards = Reward.objects.filter(
        tenant=tenant,
        status='active'
    )
    
    # Apply search/filters
    search_form = RewardSearchForm(request.GET)
    
    if search_form.is_valid():
        search = search_form.cleaned_data.get('search')
        if search:
            rewards = rewards.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )
        
        reward_type = search_form.cleaned_data.get('reward_type')
        if reward_type:
            rewards = rewards.filter(reward_type=reward_type)
        
        max_points = search_form.cleaned_data.get('max_points')
        if max_points:
            rewards = rewards.filter(points_required__lte=max_points)
        
        sort_by = search_form.cleaned_data.get('sort_by')
        if sort_by == 'points_asc':
            rewards = rewards.order_by('points_required')
        elif sort_by == 'points_desc':
            rewards = rewards.order_by('-points_required')
        elif sort_by == 'newest':
            rewards = rewards.order_by('-created_at')
        elif sort_by == 'popular':
            rewards = rewards.annotate(
                redemption_count=Count('redemptions')
            ).order_by('-redemption_count')
    
    # Pagination
    paginator = Paginator(rewards, 12)  # 12 rewards per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get customer's available points
    customer_points = tenant_customer.loyalty_points
    
    # Get customer's redemption history count
    redemption_count = Redemption.objects.filter(
        tenant_customer=tenant_customer
    ).count()
    
    # Get featured rewards
    featured_rewards = Reward.objects.filter(
        tenant=tenant,
        status='active',
        is_featured=True
    )[:3]
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'rewards': page_obj,
        'customer_points': customer_points,
        'redemption_count': redemption_count,
        'featured_rewards': featured_rewards,
        'search_form': search_form,
    }
    
    return render(request, 'rewards/catalog.html', context)


@login_required(login_url='dashboard:login')
def reward_detail(request, reward_id):
    """
    Customer view: Detailed reward information
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to load reward details.')
        return redirect('rewards:catalog')
    
    # Get customer-tenant relationship
    try:
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
    except TenantCustomer.DoesNotExist:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:login')
    
    # Get reward
    reward = get_object_or_404(Reward, id=reward_id, tenant=tenant)
    
    # Check if customer can redeem
    can_redeem, message = reward.can_be_redeemed_by(tenant_customer)
    
    # Get customer's previous redemptions of this reward
    previous_redemptions = Redemption.objects.filter(
        reward=reward,
        tenant_customer=tenant_customer
    ).order_by('-redeemed_at')[:5]
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'reward': reward,
        'can_redeem': can_redeem,
        'redemption_message': message,
        'previous_redemptions': previous_redemptions,
    }
    
    return render(request, 'rewards/detail.html', context)


@login_required(login_url='dashboard:login')
def redeem_reward(request, reward_id):
    """
    Customer action: Redeem a reward
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to process redemption.')
        return redirect('rewards:catalog')
    
    # Get customer-tenant relationship
    try:
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
    except TenantCustomer.DoesNotExist:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:login')
    
    # Get reward
    reward = get_object_or_404(Reward, id=reward_id, tenant=tenant)
    
    # Check if customer can redeem
    can_redeem, message = reward.can_be_redeemed_by(tenant_customer)
    
    if not can_redeem:
        messages.error(request, f'Cannot redeem: {message}')
        return redirect('rewards:detail', reward_id=reward_id)
    
    if request.method == 'POST':
        form = RedemptionForm(request.POST)
        if form.is_valid():
            # Create redemption
            redemption = form.save(commit=False)
            redemption.reward = reward
            redemption.tenant = tenant
            redemption.tenant_customer = tenant_customer
            redemption.customer = request.user
            redemption.points_spent = reward.points_required
            redemption.status = 'approved'  # Auto-approve for now
            redemption.save()
            
            # Deduct points from customer
            tenant_customer.loyalty_points -= reward.points_required
            tenant_customer.save(update_fields=['loyalty_points', 'updated_at'])
            
            # Increment reward redemption count
            reward.increment_redemption_count()
            
            messages.success(
                request,
                f'Successfully redeemed {reward.name}! Your redemption code is: {redemption.redemption_code}'
            )
            return redirect('rewards:my_redemptions')
    else:
        form = RedemptionForm()
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'reward': reward,
        'form': form,
    }
    
    return render(request, 'rewards/redeem.html', context)


@login_required(login_url='dashboard:login')
def my_redemptions(request):
    """
    Customer view: My redemption history
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to load redemptions.')
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
    
    # Get all redemptions
    redemptions = Redemption.objects.filter(
        tenant_customer=tenant_customer
    ).select_related('reward').order_by('-redeemed_at')
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        redemptions = redemptions.filter(status=status_filter)
    
    # Pagination
    paginator = Paginator(redemptions, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    total_points_spent = sum(r.points_spent for r in redemptions)
    active_redemptions = redemptions.filter(status__in=['pending', 'approved']).count()
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'redemptions': page_obj,
        'status_filter': status_filter,
        'total_points_spent': total_points_spent,
        'active_redemptions': active_redemptions,
    }
    
    return render(request, 'rewards/my_redemptions.html', context)


@login_required(login_url='dashboard:login')
def redemption_detail_customer(request, redemption_id):
    """
    Customer view: View redemption details
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to load redemption.')
        return redirect('rewards:my_redemptions')
    
    # Get customer-tenant relationship
    try:
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
    except TenantCustomer.DoesNotExist:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:login')
    
    # Get redemption (must belong to this customer)
    redemption = get_object_or_404(
        Redemption,
        id=redemption_id,
        tenant_customer=tenant_customer
    )
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'redemption': redemption,
    }
    
    return render(request, 'rewards/redemption_detail.html', context)


# =============================================================================
# BUSINESS OWNER VIEWS - Rewards Management
# =============================================================================

@login_required(login_url='dashboard:login')
def manage_rewards(request):
    """
    Business owner: List all rewards
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to load rewards management.')
        return redirect('dashboard:home')
    
    # Verify permissions
    try:
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
        
        if not tenant_customer.is_staff_member:
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('dashboard:home')
    except TenantCustomer.DoesNotExist:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:login')
    
    # Get all rewards for this tenant
    rewards = Reward.objects.filter(tenant=tenant).order_by('display_order', '-created_at')
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        rewards = rewards.filter(status=status_filter)
    
    # Search
    search_query = request.GET.get('search')
    if search_query:
        rewards = rewards.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(rewards, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    total_rewards = Reward.objects.filter(tenant=tenant).count()
    active_rewards = Reward.objects.filter(tenant=tenant, status='active').count()
    total_redemptions = Redemption.objects.filter(tenant=tenant).count()
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'is_business_view': True,
        'rewards': page_obj,
        'status_filter': status_filter,
        'search_query': search_query,
        'total_rewards': total_rewards,
        'active_rewards': active_rewards,
        'total_redemptions': total_redemptions,
    }
    
    return render(request, 'rewards/business_rewards.html', context)


@login_required(login_url='dashboard:login')
def create_reward(request):
    """
    Business owner: Create new reward
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to create reward.')
        return redirect('dashboard:home')
    
    # Verify permissions
    try:
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
        
        if not tenant_customer.is_staff_member:
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('dashboard:home')
    except TenantCustomer.DoesNotExist:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:login')
    
    if request.method == 'POST':
        form = RewardForm(request.POST, request.FILES)
        if form.is_valid():
            reward = form.save(commit=False)
            reward.tenant = tenant
            reward.created_by = request.user
            reward.save()
            
            messages.success(request, f'Reward "{reward.name}" has been created successfully.')
            return redirect('rewards:manage')
    else:
        form = RewardForm()
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'is_business_view': True,
        'form': form,
        'action': 'Create',
    }
    
    return render(request, 'rewards/business_reward_form.html', context)


@login_required(login_url='dashboard:login')
def edit_reward(request, reward_id):
    """
    Business owner: Edit existing reward
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to edit reward.')
        return redirect('rewards:manage')
    
    # Verify permissions
    try:
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
        
        if not tenant_customer.is_staff_member:
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('dashboard:home')
    except TenantCustomer.DoesNotExist:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:login')
    
    # Get reward
    reward = get_object_or_404(Reward, id=reward_id, tenant=tenant)
    
    if request.method == 'POST':
        form = RewardForm(request.POST, request.FILES, instance=reward)
        if form.is_valid():
            form.save()
            messages.success(request, f'Reward "{reward.name}" has been updated successfully.')
            return redirect('rewards:manage')
    else:
        form = RewardForm(instance=reward)
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'is_business_view': True,
        'form': form,
        'reward': reward,
        'action': 'Edit',
    }
    
    return render(request, 'rewards/business_reward_form.html', context)


@login_required(login_url='dashboard:login')
def delete_reward(request, reward_id):
    """
    Business owner: Delete reward
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to delete reward.')
        return redirect('rewards:manage')
    
    # Verify permissions
    try:
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
        
        if not tenant_customer.is_staff_member:
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('dashboard:home')
    except TenantCustomer.DoesNotExist:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:login')
    
    # Get reward
    reward = get_object_or_404(Reward, id=reward_id, tenant=tenant)
    
    if request.method == 'POST':
        reward_name = reward.name
        
        # Check if reward has any redemptions
        redemption_count = Redemption.objects.filter(reward=reward).count()
        if redemption_count > 0:
            # Don't delete, just deactivate
            reward.status = 'inactive'
            reward.save()
            messages.warning(
                request,
                f'Reward "{reward_name}" has been deactivated (has {redemption_count} redemptions).'
            )
        else:
            reward.delete()
            messages.success(request, f'Reward "{reward_name}" has been deleted.')
        
        return redirect('rewards:manage')
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'is_business_view': True,
        'reward': reward,
    }
    
    return render(request, 'rewards/business_reward_delete.html', context)


@login_required(login_url='dashboard:login')
def manage_redemptions(request):
    """
    Business owner: View and manage all redemptions
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to load redemptions.')
        return redirect('dashboard:home')
    
    # Verify permissions
    try:
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
        
        if not tenant_customer.is_staff_member:
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('dashboard:home')
    except TenantCustomer.DoesNotExist:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:login')
    
    # Get all redemptions
    redemptions = Redemption.objects.filter(
        tenant=tenant
    ).select_related('reward', 'customer', 'tenant_customer').order_by('-redeemed_at')
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        redemptions = redemptions.filter(status=status_filter)
    
    # Search
    search_query = request.GET.get('search')
    if search_query:
        redemptions = redemptions.filter(
            Q(redemption_code__icontains=search_query) |
            Q(customer__first_name__icontains=search_query) |
            Q(customer__last_name__icontains=search_query) |
            Q(customer__email__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(redemptions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    pending_redemptions = Redemption.objects.filter(tenant=tenant, status='pending').count()
    approved_redemptions = Redemption.objects.filter(tenant=tenant, status='approved').count()
    used_redemptions = Redemption.objects.filter(tenant=tenant, status='used').count()
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'is_business_view': True,
        'redemptions': page_obj,
        'status_filter': status_filter,
        'search_query': search_query,
        'pending_redemptions': pending_redemptions,
        'approved_redemptions': approved_redemptions,
        'used_redemptions': used_redemptions,
    }
    
    return render(request, 'rewards/business_redemptions.html', context)


@login_required(login_url='dashboard:login')
def redemption_detail_business(request, redemption_id):
    """
    Business owner: View redemption details and manage status
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to load redemption.')
        return redirect('rewards:manage_redemptions')
    
    # Verify permissions
    try:
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
        
        if not tenant_customer.is_staff_member:
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('dashboard:home')
    except TenantCustomer.DoesNotExist:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:login')
    
    # Get redemption
    redemption = get_object_or_404(Redemption, id=redemption_id, tenant=tenant)
    
    # Handle status changes
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'use':
            redemption.use(staff_member=request.user)
            messages.success(request, f'Redemption {redemption.redemption_code} marked as used.')
            return redirect('rewards:manage_redemptions')
        
        elif action == 'cancel':
            redemption.cancel(refund_points=True)
            messages.success(request, f'Redemption {redemption.redemption_code} has been cancelled and points refunded.')
            return redirect('rewards:manage_redemptions')
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'is_business_view': True,
        'redemption': redemption,
    }
    
    return render(request, 'rewards/business_redemption_detail.html', context)


@login_required(login_url='dashboard:login')
def use_redemption_quick(request):
    """
    Business owner: Quick form to mark redemption as used by code
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        return JsonResponse({'success': False, 'error': 'Invalid tenant'})
    
    # Verify permissions
    try:
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
        
        if not tenant_customer.is_staff_member:
            return JsonResponse({'success': False, 'error': 'Permission denied'})
    except TenantCustomer.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Access denied'})
    
    if request.method == 'POST':
        form = RedemptionUseForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['redemption_code'].upper()
            
            try:
                redemption = Redemption.objects.get(
                    redemption_code=code,
                    tenant=tenant
                )
                
                # Check if can be used
                if redemption.status not in ['pending', 'approved']:
                    return JsonResponse({
                        'success': False,
                        'error': f'This redemption cannot be used (status: {redemption.get_status_display()})'
                    })
                
                if not redemption.is_valid:
                    return JsonResponse({
                        'success': False,
                        'error': 'This redemption has expired or is not yet valid'
                    })
                
                # Mark as used
                redemption.use(staff_member=request.user)
                
                return JsonResponse({
                    'success': True,
                    'message': f'Redemption {code} marked as used successfully!',
                    'customer': redemption.customer.get_full_name(),
                    'reward': redemption.reward.name
                })
                
            except Redemption.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid redemption code'
                })
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            })
    
    # GET request - show form
    form = RedemptionUseForm()
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'is_business_view': True,
        'form': form,
    }
    
    return render(request, 'rewards/quick_use.html', context)
