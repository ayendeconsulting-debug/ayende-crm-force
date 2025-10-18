"""
Enhanced Customer Profile Forms
"""

from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from customers.models import Customer, TenantCustomer


class EnhancedProfileForm(forms.ModelForm):
    """
    Enhanced profile form with additional fields
    """
    
    class Meta:
        model = Customer
        fields = [
            'profile_picture',
            'first_name',
            'last_name',
            'phone',
            'date_of_birth',
            'address',
            'city',
            'postal_code',
            'country',
            'preferred_language',
        ]
        
        widgets = {
            'profile_picture': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'First Name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Last Name'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+1 234 567 8900'
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Street address'
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'City'
            }),
            'postal_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Postal Code'
            }),
            'country': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Country'
            }),
            'preferred_language': forms.Select(attrs={
                'class': 'form-control'
            }),
        }


class CustomerPreferencesForm(forms.ModelForm):
    """
    Customer preferences for notifications and communications
    """
    
    class Meta:
        model = TenantCustomer
        fields = [
            'email_notifications',
            'sms_notifications',
            'push_notifications',
        ]
        
        widgets = {
            'email_notifications': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'sms_notifications': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'push_notifications': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
        
        labels = {
            'email_notifications': 'Receive email notifications',
            'sms_notifications': 'Receive SMS notifications',
            'push_notifications': 'Receive push notifications',
        }
        
        help_texts = {
            'email_notifications': 'Get notified about promotions and updates via email',
            'sms_notifications': 'Get SMS alerts for important updates',
            'push_notifications': 'Receive push notifications in the app',
        }


class CustomPasswordChangeForm(PasswordChangeForm):
    """
    Custom password change form with better styling
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['old_password'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Current Password'
        })
        self.fields['new_password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'New Password'
        })
        self.fields['new_password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Confirm New Password'
        })


class ProfilePictureForm(forms.ModelForm):
    """
    Separate form for profile picture upload
    """
    
    class Meta:
        model = Customer
        fields = ['profile_picture']
        
        widgets = {
            'profile_picture': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*',
                'id': 'profilePictureInput'
            })
        }
    
    def clean_profile_picture(self):
        picture = self.cleaned_data.get('profile_picture')
        
        if picture:
            # Check file size (max 5MB)
            if picture.size > 5 * 1024 * 1024:
                raise forms.ValidationError('Image file too large (max 5MB)')
            
            # Check file type
            if not picture.content_type.startswith('image/'):
                raise forms.ValidationError('File must be an image')
        
        return picture


class DeleteAccountForm(forms.Form):
    """
    Form to confirm account deletion
    """
    
    confirm_email = forms.EmailField(
        label='Confirm your email address',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email to confirm'
        })
    )
    
    password = forms.CharField(
        label='Enter your password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password'
        })
    )
    
    confirm_deletion = forms.BooleanField(
        label='I understand this action cannot be undone',
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
