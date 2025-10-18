"""
Enhanced Customer Profile Views
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from customers.models import TenantCustomer
from .forms import (
    EnhancedProfileForm,
    CustomerPreferencesForm,
    CustomPasswordChangeForm,
    ProfilePictureForm,
    DeleteAccountForm
)


@login_required(login_url='dashboard:login')
def enhanced_profile(request):
    """
    Enhanced profile view with tabs for different sections
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to load profile.')
        return redirect('dashboard:home')
    
    # Get tenant-customer relationship
    try:
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
    except TenantCustomer.DoesNotExist:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:login')
    
    # Calculate profile completion
    completion_percentage = calculate_profile_completion(request.user)
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'completion_percentage': completion_percentage,
        'profile_sections': get_profile_sections(request.user),
    }
    
    return render(request, 'profile/enhanced_profile.html', context)


@login_required(login_url='dashboard:login')
def edit_profile_info(request):
    """
    Edit basic profile information
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to update profile.')
        return redirect('dashboard:home')
    
    try:
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
    except TenantCustomer.DoesNotExist:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:login')
    
    if request.method == 'POST':
        form = EnhancedProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile:enhanced_profile')
    else:
        form = EnhancedProfileForm(instance=request.user)
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'form': form,
    }
    
    return render(request, 'profile/edit_info.html', context)


@login_required(login_url='dashboard:login')
def edit_preferences(request):
    """
    Edit notification preferences
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to update preferences.')
        return redirect('dashboard:home')
    
    try:
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
    except TenantCustomer.DoesNotExist:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:login')
    
    if request.method == 'POST':
        form = CustomerPreferencesForm(request.POST, instance=tenant_customer)
        if form.is_valid():
            form.save()
            messages.success(request, 'Preferences updated successfully!')
            return redirect('profile:enhanced_profile')
    else:
        form = CustomerPreferencesForm(instance=tenant_customer)
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'form': form,
    }
    
    return render(request, 'profile/edit_preferences.html', context)


@login_required(login_url='dashboard:login')
def change_password(request):
    """
    Change password
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to change password.')
        return redirect('dashboard:home')
    
    try:
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
    except TenantCustomer.DoesNotExist:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:login')
    
    if request.method == 'POST':
        form = CustomPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Keep user logged in
            messages.success(request, 'Password changed successfully!')
            return redirect('profile:enhanced_profile')
    else:
        form = CustomPasswordChangeForm(request.user)
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'form': form,
    }
    
    return render(request, 'profile/change_password.html', context)


@login_required(login_url='dashboard:login')
def upload_profile_picture(request):
    """
    Upload/change profile picture
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to upload picture.')
        return redirect('dashboard:home')
    
    try:
        tenant_customer = TenantCustomer.objects.get(
            customer=request.user,
            tenant=tenant
        )
    except TenantCustomer.DoesNotExist:
        messages.error(request, 'Access denied.')
        return redirect('dashboard:login')
    
    if request.method == 'POST':
        form = ProfilePictureForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile picture updated successfully!')
            return redirect('profile:enhanced_profile')
    else:
        form = ProfilePictureForm(instance=request.user)
    
    context = {
        'tenant': tenant,
        'tenant_customer': tenant_customer,
        'form': form,
    }
    
    return render(request, 'profile/upload_picture.html', context)


@login_required(login_url='dashboard:login')
def delete_profile_picture(request):
    """
    Delete profile picture
    """
    tenant = getattr(request, 'tenant', None)
    
    if not tenant:
        messages.error(request, 'Unable to delete picture.')
        return redirect('profile:enhanced_profile')
    
    if request.method == 'POST':
        request.user.profile_picture.delete()
        request.user.save()
        messages.success(request, 'Profile picture removed successfully!')
    
    return redirect('profile:enhanced_profile')


def calculate_profile_completion(user):
    """
    Calculate profile completion percentage
    """
    fields_to_check = [
        'first_name',
        'last_name',
        'email',
        'phone',
        'date_of_birth',
        'address',
        'city',
        'postal_code',
        'country',
        'profile_picture',
    ]
    
    completed = 0
    total = len(fields_to_check)
    
    for field in fields_to_check:
        value = getattr(user, field, None)
        if value:
            if field == 'profile_picture':
                # Check if file exists
                if value and hasattr(value, 'url'):
                    completed += 1
            else:
                # Check if field has content
                if str(value).strip():
                    completed += 1
    
    return int((completed / total) * 100)


def get_profile_sections(user):
    """
    Get completion status for each profile section
    """
    sections = {
        'basic_info': {
            'name': 'Basic Information',
            'fields': ['first_name', 'last_name', 'email', 'phone'],
            'completed': 0,
            'total': 4
        },
        'address': {
            'name': 'Address',
            'fields': ['address', 'city', 'postal_code', 'country'],
            'completed': 0,
            'total': 4
        },
        'personal': {
            'name': 'Personal Details',
            'fields': ['date_of_birth', 'profile_picture'],
            'completed': 0,
            'total': 2
        }
    }
    
    for section_key, section_data in sections.items():
        for field in section_data['fields']:
            value = getattr(user, field, None)
            if value:
                if field == 'profile_picture':
                    if value and hasattr(value, 'url'):
                        section_data['completed'] += 1
                else:
                    if str(value).strip():
                        section_data['completed'] += 1
        
        # Calculate percentage
        section_data['percentage'] = int(
            (section_data['completed'] / section_data['total']) * 100
        )
    
    return sections
