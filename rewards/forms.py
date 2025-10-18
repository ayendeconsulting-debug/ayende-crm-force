"""
Forms for Rewards Management
"""

from django import forms
from .models import Reward, Redemption


class RewardForm(forms.ModelForm):
    """
    Form for business owners to create/edit rewards
    """
    
    class Meta:
        model = Reward
        fields = [
            'name',
            'description',
            'reward_type',
            'image',
            'points_required',
            'discount_type',
            'discount_value',
            'minimum_purchase',
            'has_stock_limit',
            'total_stock',
            'has_expiration',
            'expires_at',
            'limit_per_customer',
            'validity_days',
            'status',
            'is_featured',
            'terms_conditions',
            'display_order',
        ]
        
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., $5 Off Next Purchase'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe this reward...'
            }),
            'reward_type': forms.Select(attrs={'class': 'form-control'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'points_required': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1
            }),
            'discount_type': forms.Select(attrs={'class': 'form-control'}),
            'discount_value': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': 0
            }),
            'minimum_purchase': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': 0
            }),
            'has_stock_limit': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'total_stock': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0
            }),
            'has_expiration': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'expires_at': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'limit_per_customer': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0
            }),
            'validity_days': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0
            }),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'is_featured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'terms_conditions': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
            'display_order': forms.NumberInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Make certain fields not required initially
        self.fields['discount_type'].required = False
        self.fields['discount_value'].required = False
        self.fields['minimum_purchase'].required = False
        self.fields['expires_at'].required = False
        self.fields['total_stock'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Validate discount fields for discount type rewards
        reward_type = cleaned_data.get('reward_type')
        if reward_type == 'discount':
            discount_type = cleaned_data.get('discount_type')
            discount_value = cleaned_data.get('discount_value')
            
            if not discount_type:
                self.add_error('discount_type', 'Discount type is required for discount rewards')
            
            if not discount_value or discount_value <= 0:
                self.add_error('discount_value', 'Discount value must be greater than 0')
        
        # Validate stock fields
        has_stock_limit = cleaned_data.get('has_stock_limit')
        total_stock = cleaned_data.get('total_stock')
        
        if has_stock_limit and (total_stock is None or total_stock <= 0):
            self.add_error('total_stock', 'Total stock must be greater than 0 when stock limit is enabled')
        
        # Validate expiration
        has_expiration = cleaned_data.get('has_expiration')
        expires_at = cleaned_data.get('expires_at')
        
        if has_expiration and not expires_at:
            self.add_error('expires_at', 'Expiration date is required when expiration is enabled')
        
        return cleaned_data


class RedemptionForm(forms.ModelForm):
    """
    Form for customers to redeem rewards
    """
    
    class Meta:
        model = Redemption
        fields = ['customer_note']
        
        widgets = {
            'customer_note': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Any special requests or notes? (optional)'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['customer_note'].required = False


class RedemptionApprovalForm(forms.ModelForm):
    """
    Form for business owners to approve/reject redemptions
    """
    
    action = forms.ChoiceField(
        choices=[
            ('approve', 'Approve'),
            ('reject', 'Reject'),
        ],
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    
    class Meta:
        model = Redemption
        fields = ['staff_note', 'rejection_reason']
        
        widgets = {
            'staff_note': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Internal notes...'
            }),
            'rejection_reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Reason for rejection (shown to customer)...'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['staff_note'].required = False
        self.fields['rejection_reason'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        rejection_reason = cleaned_data.get('rejection_reason')
        
        if action == 'reject' and not rejection_reason:
            self.add_error('rejection_reason', 'Rejection reason is required when rejecting a redemption')
        
        return cleaned_data


class RedemptionUseForm(forms.Form):
    """
    Quick form to mark redemption as used
    """
    
    redemption_code = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter redemption code (e.g., RWD-ABC123)',
            'autofocus': True
        })
    )
    
    staff_note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Optional notes...'
        })
    )


class RewardSearchForm(forms.Form):
    """
    Search and filter form for rewards catalog
    """
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search rewards...'
        })
    )
    
    reward_type = forms.ChoiceField(
        required=False,
        choices=[('', 'All Types')] + Reward.REWARD_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    max_points = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Max points',
            'min': 0
        })
    )
    
    sort_by = forms.ChoiceField(
        required=False,
        choices=[
            ('points_asc', 'Points: Low to High'),
            ('points_desc', 'Points: High to Low'),
            ('newest', 'Newest First'),
            ('popular', 'Most Popular'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
