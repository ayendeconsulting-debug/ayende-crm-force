from django import forms
from customers.models import Customer, TenantCustomer
from django.core.exceptions import ValidationError
import re


class CustomerRegistrationForm(forms.Form):
    """
    Customer self-registration form.
    """
    email = forms.EmailField(
        max_length=255,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'your.email@example.com'
        }),
        label='Email Address'
    )
    
    first_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'John'
        }),
        label='First Name'
    )
    
    last_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Doe'
        }),
        label='Last Name'
    )
    
    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+1 (555) 123-4567'
        }),
        label='Phone Number'
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Create a strong password'
        }),
        label='Password',
        help_text='Password must be at least 8 characters long.'
    )
    
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Re-enter your password'
        }),
        label='Confirm Password'
    )
    
    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        # Note: For registration, we need to check across all tenants or implement tenant-specific registration
        # For now, allow same email across different tenants
        return email
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        
        if password and password_confirm and password != password_confirm:
            raise ValidationError('Passwords do not match.')
        
        if password and len(password) < 8:
            raise ValidationError('Password must be at least 8 characters long.')
        
        return cleaned_data
    
    def save(self):
        """Create customer and link to tenant."""
        # Create customer
        customer = Customer.objects.create_user(
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password'],
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            phone=self.cleaned_data.get('phone', '')
        )
        
        # Link to tenant
        TenantCustomer.objects.create(
            customer=customer,
            tenant=self.tenant,
            role='customer',
            is_active=True
        )
        
        return customer


class CustomerLoginForm(forms.Form):
    """
    Customer login form.
    """
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'your.email@example.com'
        }),
        label='Email Address'
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password'
        }),
        label='Password'
    )
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)


class CustomerProfileForm(forms.ModelForm):
    """
    Customer profile update form.
    """
    class Meta:
        model = TenantCustomer
        fields = ['phone', 'email', 'address', 'city', 'state', 'postal_code', 'date_of_birth', 'profile_picture', 'preferred_language']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'John'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Doe'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+1 (555) 123-4567'
            }),
        }


class BusinessCustomerAddForm(forms.Form):
    """
    Business owner form to manually add a new customer.
    """
    email = forms.EmailField(
        max_length=255,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'customer@example.com'
        }),
        label='Email Address',
        help_text='Customer will use this to login'
    )
    
    first_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'John'
        }),
        label='First Name'
    )
    
    last_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Doe'
        }),
        label='Last Name'
    )
    
    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+1 (555) 123-4567'
        }),
        label='Phone Number'
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Create temporary password'
        }),
        label='Temporary Password',
        help_text='Customer can change this after first login.'
    )
    
    loyalty_points = forms.IntegerField(
        initial=0,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0'
        }),
        label='Initial Loyalty Points',
        help_text='Starting points for this customer (optional)'
    )
    
    is_vip = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label='VIP Status',
        help_text='Mark this customer as VIP'
    )
    
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Internal notes about this customer...'
        }),
        label='Internal Notes',
        help_text='These notes are only visible to staff'
    )
    
    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        
        # Check if email already exists in THIS tenant (refactored architecture)
        if TenantCustomer.objects.filter(email=email, tenant=self.tenant).exists():
            raise ValidationError('This customer already exists in your system.')
        
        return email
    
    def clean_password(self):
        password = self.cleaned_data.get('password')
        if password and len(password) < 8:
            raise ValidationError('Password must be at least 8 characters long.')
        return password
    
    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '')
        if phone:
            # Remove non-digit characters for validation
            digits = re.sub(r'\D', '', phone)
            if len(digits) < 10:
                raise ValidationError('Please enter a valid phone number.')
        return phone
    
    def save(self):
        """Create TenantCustomer directly (refactored architecture)."""
        from django.contrib.auth.hashers import make_password
        
        # Create TenantCustomer directly (no separate Customer object needed)
        tenant_customer = TenantCustomer.objects.create(
            email=self.cleaned_data['email'],
            username=f"{self.cleaned_data['email']}.{self.tenant.subdomain}",
            password=make_password(self.cleaned_data['password']),
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            phone=self.cleaned_data.get('phone', ''),
            tenant=self.tenant,
            role='customer',
            is_active=True,
            loyalty_points=self.cleaned_data.get('loyalty_points', 0),
            is_vip=self.cleaned_data.get('is_vip', False),
            notes=self.cleaned_data.get('notes', ''),
            email_verified=False  # Will need email verification
        )
        
        return tenant_customer


class BusinessCustomerEditForm(forms.ModelForm):
    """
    Business owner form to edit existing customer information.
    UPDATED: Works with refactored TenantCustomer model (no separate Customer object)
    """
    # TenantCustomer fields (directly on the model)
    first_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'John'
        }),
        label='First Name'
    )
    
    last_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Doe'
        }),
        label='Last Name'
    )
    
    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+1 (555) 123-4567'
        }),
        label='Phone Number'
    )
    
    loyalty_points = forms.IntegerField(
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0'
        }),
        label='Loyalty Points',
        help_text='Adjust customer loyalty points'
    )
    
    is_vip = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label='VIP Status',
        help_text='Mark this customer as VIP'
    )
    
    is_active = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label='Active Status',
        help_text='Inactive customers cannot login'
    )
    
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Internal notes about this customer...'
        }),
        label='Internal Notes',
        help_text='These notes are only visible to staff'
    )
    
    class Meta:
        model = TenantCustomer
        fields = ['first_name', 'last_name', 'phone', 'loyalty_points', 'is_vip', 'is_active', 'notes']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Pre-populate fields from instance (TenantCustomer)
        if self.instance and self.instance.pk:
            self.fields['first_name'].initial = self.instance.first_name
            self.fields['last_name'].initial = self.instance.last_name
            self.fields['phone'].initial = self.instance.phone
    
    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '')
        if phone:
            # Remove non-digit characters for validation
            digits = re.sub(r'\D', '', phone)
            if len(digits) < 10:
                raise ValidationError('Please enter a valid phone number.')
        return phone
    
    def save(self, commit=True):
        """Save TenantCustomer with updated fields."""
        tenant_customer = super().save(commit=False)
        
        # Update fields from form
        tenant_customer.first_name = self.cleaned_data['first_name']
        tenant_customer.last_name = self.cleaned_data['last_name']
        tenant_customer.phone = self.cleaned_data.get('phone', '')
        
        if commit:
            tenant_customer.save()
        
        return tenant_customer


class CustomerNotesForm(forms.ModelForm):
    """
    Quick form to edit customer notes only.
    """
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 6,
            'placeholder': 'Add notes about this customer...'
        }),
        label='Internal Notes',
        help_text='These notes are only visible to staff members'
    )
    
    class Meta:
        model = TenantCustomer
        fields = ['notes']