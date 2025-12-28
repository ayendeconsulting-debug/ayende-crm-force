from django import forms
from .models import InvestmentLead, LeadNote, LeadActivity


class InvestmentLeadForm(forms.ModelForm):
    """
    Public-facing form for investment interest submission
    """
    
    class Meta:
        model = InvestmentLead
        fields = [
            'full_name',
            'email',
            'phone_number',
            'company_name',
            'investment_amount',
            'accredited_investor',
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'w-full border border-slate-300 rounded p-2 focus:ring-2 focus:ring-blue-500 outline-none',
                'placeholder': 'John Doe',
                'required': True
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full border border-slate-300 rounded p-2 focus:ring-2 focus:ring-blue-500 outline-none',
                'placeholder': 'john@example.com',
                'required': True
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'w-full border border-slate-300 rounded p-2 focus:ring-2 focus:ring-blue-500 outline-none',
                'placeholder': '+1 (555) 123-4567',
            }),
            'company_name': forms.TextInput(attrs={
                'class': 'w-full border border-slate-300 rounded p-2 focus:ring-2 focus:ring-blue-500 outline-none',
                'placeholder': 'Your Company',
            }),
            'investment_amount': forms.Select(attrs={
                'class': 'w-full border border-slate-300 rounded p-2 focus:ring-2 focus:ring-blue-500 outline-none'
            }),
            'accredited_investor': forms.CheckboxInput(attrs={
                'class': 'mt-1'
            }),
        }
    
    def clean_email(self):
        """Validate email doesn't already exist"""
        email = self.cleaned_data.get('email')
        if InvestmentLead.objects.filter(email=email).exists():
            raise forms.ValidationError(
                "An investment interest with this email already exists. "
                "Please contact admin@ayendecx.com if you need to update your information."
            )
        return email


class LeadNoteForm(forms.ModelForm):
    """
    Form for adding notes to leads
    """
    
    class Meta:
        model = LeadNote
        fields = ['note', 'is_pinned']
        widgets = {
            'note': forms.Textarea(attrs={
                'rows': 4,
                'class': 'w-full border border-slate-300 rounded p-2 focus:ring-2 focus:ring-blue-500 outline-none',
                'placeholder': 'Add your note here...'
            }),
            'is_pinned': forms.CheckboxInput(attrs={
                'class': 'rounded'
            })
        }


class LeadActivityForm(forms.ModelForm):
    """
    Form for adding activities to leads
    """
    
    class Meta:
        model = LeadActivity
        fields = ['activity_type', 'subject', 'description', 'outcome']
        widgets = {
            'activity_type': forms.Select(attrs={
                'class': 'w-full border border-slate-300 rounded p-2 focus:ring-2 focus:ring-blue-500 outline-none'
            }),
            'subject': forms.TextInput(attrs={
                'class': 'w-full border border-slate-300 rounded p-2 focus:ring-2 focus:ring-blue-500 outline-none',
                'placeholder': 'Activity subject'
            }),
            'description': forms.Textarea(attrs={
                'rows': 4,
                'class': 'w-full border border-slate-300 rounded p-2 focus:ring-2 focus:ring-blue-500 outline-none',
                'placeholder': 'Activity details...'
            }),
            'outcome': forms.Select(attrs={
                'class': 'w-full border border-slate-300 rounded p-2 focus:ring-2 focus:ring-blue-500 outline-none'
            }),
        }
