"""
Notification Forms for Ayende CRMForce
Forms for creating and managing notifications
"""

from django import forms
from .models import Notification, NotificationRecipient
from customers.models import TenantCustomer


class NotificationComposeForm(forms.ModelForm):
    """
    Form for composing and sending notifications.
    Business owners use this to create notifications.
    """
    
    # Target audience selection
    target_audience = forms.ChoiceField(
        label="Target Audience",
        choices=[
            ('all', 'All Active Customers'),
            ('vip', 'VIP Customers Only'),
            ('points_range', 'Customers by Points Range'),
            ('specific', 'Specific Customers'),
        ],
        widget=forms.RadioSelect,
        initial='all'
    )
    
    # Points range fields (shown conditionally)
    points_min = forms.IntegerField(
        label="Minimum Points",
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 100'
        })
    )
    
    points_max = forms.IntegerField(
        label="Maximum Points",
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 1000'
        })
    )
    
    # Specific customers selection (shown conditionally)
    specific_customers = forms.ModelMultipleChoiceField(
        queryset=TenantCustomer.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Select Customers"
    )
    
    # Send immediately or schedule
    send_option = forms.ChoiceField(
        label="When to Send",
        choices=[
            ('now', 'Send Immediately'),
            ('schedule', 'Schedule for Later'),
        ],
        widget=forms.RadioSelect,
        initial='now'
    )
    
    scheduled_datetime = forms.DateTimeField(
        label="Schedule For",
        required=False,
        widget=forms.DateTimeInput(attrs={
            'type': 'datetime-local',
            'class': 'form-control'
        }),
        help_text="Select date and time for scheduled delivery"
    )
    
    class Meta:
        model = Notification
        fields = [
            'title',
            'message',
            'category',
            'priority',
            'notes',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter notification title',
                'maxlength': 200
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': 'Enter your message here...',
            }),
            'category': forms.Select(attrs={
                'class': 'form-control'
            }),
            'priority': forms.Select(attrs={
                'class': 'form-control'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Internal notes (optional, not visible to customers)'
            }),
        }
        labels = {
            'title': 'Notification Title',
            'message': 'Message',
            'category': 'Category',
            'priority': 'Priority',
            'notes': 'Internal Notes',
        }
    
    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        
        # Set queryset for specific customers based on tenant
        if tenant:
            self.fields['specific_customers'].queryset = TenantCustomer.objects.filter(
                tenant=tenant,
                role='customer',
                is_active=True
            ).select_related('customer').order_by('customer__first_name', 'customer__last_name')
        
        # Make all fields required except notes
        self.fields['notes'].required = False
        self.fields['priority'].initial = 'normal'
    
    def clean(self):
        cleaned_data = super().clean()
        target_audience = cleaned_data.get('target_audience')
        send_option = cleaned_data.get('send_option')
        
        # Validate points range
        if target_audience == 'points_range':
            points_min = cleaned_data.get('points_min')
            points_max = cleaned_data.get('points_max')
            
            if points_min is None and points_max is None:
                raise forms.ValidationError(
                    "Please specify at least a minimum or maximum points value."
                )
            
            if points_min is not None and points_max is not None:
                if points_min > points_max:
                    raise forms.ValidationError(
                        "Minimum points cannot be greater than maximum points."
                    )
        
        # Validate specific customers selection
        if target_audience == 'specific':
            specific_customers = cleaned_data.get('specific_customers')
            if not specific_customers:
                raise forms.ValidationError(
                    "Please select at least one customer for targeted notifications."
                )
        
        # Validate scheduled datetime
        if send_option == 'schedule':
            scheduled_datetime = cleaned_data.get('scheduled_datetime')
            if not scheduled_datetime:
                raise forms.ValidationError(
                    "Please specify a date and time for scheduled delivery."
                )
            
            from django.utils import timezone
            if scheduled_datetime <= timezone.now():
                raise forms.ValidationError(
                    "Scheduled time must be in the future."
                )
        
        return cleaned_data
    
    def save(self, commit=True):
        notification = super().save(commit=False)
        
        # Set tenant
        if self.tenant:
            notification.tenant = self.tenant
        
        # Set targeting based on target_audience selection
        target_audience = self.cleaned_data.get('target_audience')
        
        if target_audience == 'all':
            notification.target_all_customers = True
            notification.target_vip_only = False
            notification.target_min_points = None
            notification.target_max_points = None
        
        elif target_audience == 'vip':
            notification.target_all_customers = True
            notification.target_vip_only = True
            notification.target_min_points = None
            notification.target_max_points = None
        
        elif target_audience == 'points_range':
            notification.target_all_customers = True
            notification.target_vip_only = False
            notification.target_min_points = self.cleaned_data.get('points_min')
            notification.target_max_points = self.cleaned_data.get('points_max')
        
        elif target_audience == 'specific':
            notification.target_all_customers = False
            notification.target_vip_only = False
            notification.target_min_points = None
            notification.target_max_points = None
        
        # Set scheduling
        send_option = self.cleaned_data.get('send_option')
        if send_option == 'schedule':
            notification.status = 'scheduled'
            notification.scheduled_for = self.cleaned_data.get('scheduled_datetime')
        else:
            notification.status = 'draft'  # Will be sent immediately after save
        
        if commit:
            notification.save()
            
            # Handle many-to-many relationship for specific customers
            if target_audience == 'specific':
                specific_customers = self.cleaned_data.get('specific_customers')
                notification.target_specific_customers.set(specific_customers)
        
        return notification


class NotificationQuickReplyForm(forms.Form):
    """
    Quick reply form for customers to respond to notifications.
    (Optional feature for future enhancement)
    """
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Type your message...'
        }),
        max_length=500
    )
