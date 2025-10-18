from django import forms
from django.contrib.auth import authenticate
from customers.models import Customer, TenantCustomer


class CustomerRegistrationForm(forms.ModelForm):
    """
    Form for customer self-registration.
    Professional, no emojis.
    """
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Create a password'
        }),
        min_length=8,
        help_text='Password must be at least 8 characters'
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm your password'
        }),
        label='Confirm Password'
    )
    
    class Meta:
        model = Customer
        fields = ['email', 'first_name', 'last_name', 'phone']
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'your.email@example.com'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'First name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Last name'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+1 (555) 123-4567'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if Customer.objects.filter(email=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        
        if password and password_confirm:
            if password != password_confirm:
                raise forms.ValidationError('Passwords do not match.')
        
        return cleaned_data
    
    def save(self, commit=True):
        customer = super().save(commit=False)
        customer.set_password(self.cleaned_data['password'])
        customer.username = self.cleaned_data['email']  # Set username to email
        
        if commit:
            customer.save()
            
            # Automatically link customer to tenant if tenant is provided
            if self.tenant:
                TenantCustomer.objects.create(
                    customer=customer,
                    tenant=self.tenant,
                    role='customer',
                    email_notifications=True,
                    push_notifications=True
                )
        
        return customer


class CustomerLoginForm(forms.Form):
    """
    Form for customer login.
    Professional, no emojis.
    """
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'your.email@example.com',
            'autofocus': True
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Your password'
        })
    )
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
    
    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        password = cleaned_data.get('password')
        
        if email and password:
            # Authenticate using email
            user = authenticate(
                request=self.request,
                username=email,
                password=password
            )
            
            if user is None:
                raise forms.ValidationError('Invalid email or password.')
        
        return cleaned_data


class CustomerProfileForm(forms.ModelForm):
    """
    Form for customer profile editing - WITHOUT avatar field.
    """
    class Meta:
        model = Customer
        fields = ['first_name', 'last_name', 'phone']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
        }