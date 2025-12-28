import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

class InvestmentLead(models.Model):
    """
    Core investment lead model with automatic scoring and prioritization.
    Tracks potential investors from initial contact through conversion.
    """
    
    INVESTMENT_CHOICES = [
        ('5000', '$5,000 (Believer)'),
        ('10000', '$10,000 (Early Supporter)'),
        ('25000', '$25,000+ (Founding Circle)'),
    ]
    
    STATUS_CHOICES = [
        ('new', 'New Lead'),
        ('contacted', 'Contacted'),
        ('qualified', 'Qualified'),
        ('negotiating', 'Negotiating'),
        ('converted', 'Converted'),
        ('lost', 'Lost'),
        ('on_hold', 'On Hold'),
    ]
    
    PRIORITY_CHOICES = [
        ('hot', 'Hot'),
        ('warm', 'Warm'),
        ('cold', 'Cold'),
    ]
    
    SOURCE_CHOICES = [
        ('website', 'Website Form'),
        ('referral', 'Referral'),
        ('direct', 'Direct Contact'),
        ('event', 'Event'),
        ('linkedin', 'LinkedIn'),
        ('other', 'Other'),
    ]
    
    # Primary Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=255, db_index=True)
    email = models.EmailField(unique=True, db_index=True)
    phone_number = models.CharField(max_length=20, blank=True)
    company_name = models.CharField(max_length=255, blank=True)
    linkedin_profile = models.URLField(blank=True)
    
    # Investment Details
    investment_amount = models.CharField(
        max_length=10, 
        choices=INVESTMENT_CHOICES,
        help_text="Intended investment amount"
    )
    accredited_investor = models.BooleanField(
        default=False,
        help_text="Certified accredited investor status"
    )
    
    # Lead Management
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='new',
        db_index=True
    )
    lead_score = models.IntegerField(
        default=0,
        help_text="Auto-calculated score (0-100)"
    )
    priority = models.CharField(
        max_length=10, 
        choices=PRIORITY_CHOICES, 
        default='warm',
        db_index=True
    )
    
    # Assignment & Follow-up
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='assigned_investment_leads',
        help_text="Sales team member assigned to this lead"
    )
    last_contacted_at = models.DateTimeField(null=True, blank=True)
    next_follow_up_date = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Suggested next follow-up date"
    )
    follow_up_count = models.IntegerField(
        default=0,
        help_text="Number of follow-up attempts"
    )
    
    # Tracking & Analytics
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    source = models.CharField(
        max_length=50, 
        choices=SOURCE_CHOICES,
        default='website'
    )
    referral_source = models.CharField(max_length=255, blank=True)
    utm_source = models.CharField(max_length=100, blank=True)
    utm_campaign = models.CharField(max_length=100, blank=True)
    utm_medium = models.CharField(max_length=100, blank=True)
    
    # Conversion Tracking
    converted_at = models.DateTimeField(null=True, blank=True)
    conversion_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Actual converted investment amount"
    )
    lost_reason = models.TextField(
        blank=True,
        help_text="Reason if lead was lost"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Investment Lead'
        verbose_name_plural = 'Investment Leads'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at', 'status']),
            models.Index(fields=['priority', '-lead_score']),
            models.Index(fields=['assigned_to', 'status']),
        ]
    
    def __str__(self):
        return f"{self.full_name} - ${self.investment_amount} ({self.get_status_display()})"
    
    def calculate_score(self):
        """
        Calculate lead score based on multiple factors.
        Score range: 0-100
        """
        score = 0
        
        # Investment amount (40 points max)
        if self.investment_amount == '25000':
            score += 40
        elif self.investment_amount == '10000':
            score += 20
        elif self.investment_amount == '5000':
            score += 10
        
        # Accredited investor status (30 points)
        if self.accredited_investor:
            score += 30
        
        # Complete profile (20 points)
        profile_complete = 0
        if self.full_name:
            profile_complete += 1
        if self.email:
            profile_complete += 1
        if self.phone_number:
            profile_complete += 1
        if self.company_name:
            profile_complete += 1
        if self.linkedin_profile:
            profile_complete += 1
        
        score += (profile_complete / 5) * 20
        
        # Source quality (10 points)
        if self.source in ['referral', 'direct']:
            score += 10
        elif self.source == 'event':
            score += 5
        
        return int(score)
    
    def calculate_priority(self):
        """Auto-assign priority based on lead score"""
        if self.lead_score >= 80:
            return 'hot'
        elif self.lead_score >= 50:
            return 'warm'
        else:
            return 'cold'
    
    def calculate_next_follow_up(self):
        """
        Calculate suggested next follow-up date based on priority.
        Hot: Tomorrow
        Warm: 3 days
        Cold: 7 days
        """
        if self.priority == 'hot':
            return timezone.now().date() + timedelta(days=1)
        elif self.priority == 'warm':
            return timezone.now().date() + timedelta(days=3)
        else:  # cold
            return timezone.now().date() + timedelta(days=7)
    
    def save(self, *args, **kwargs):
        """Override save to auto-calculate score, priority, and follow-up date"""
        
        # Calculate lead score
        self.lead_score = self.calculate_score()
        
        # Auto-assign priority
        self.priority = self.calculate_priority()
        
        # Set next follow-up date if not already set and status is new
        if not self.next_follow_up_date and self.status == 'new':
            self.next_follow_up_date = self.calculate_next_follow_up()
        
        # Track conversion timestamp
        if self.status == 'converted' and not self.converted_at:
            self.converted_at = timezone.now()
        
        super().save(*args, **kwargs)
    
    def get_investment_amount_display_value(self):
        """Return numeric value of investment amount"""
        return int(self.investment_amount)
    
    def get_priority_badge_color(self):
        """Return CSS class for priority badge"""
        colors = {
            'hot': 'bg-red-100 text-red-800',
            'warm': 'bg-yellow-100 text-yellow-800',
            'cold': 'bg-blue-100 text-blue-800',
        }
        return colors.get(self.priority, 'bg-gray-100 text-gray-800')
    
    def get_status_badge_color(self):
        """Return CSS class for status badge"""
        colors = {
            'new': 'bg-blue-100 text-blue-800',
            'contacted': 'bg-purple-100 text-purple-800',
            'qualified': 'bg-green-100 text-green-800',
            'negotiating': 'bg-yellow-100 text-yellow-800',
            'converted': 'bg-green-600 text-white',
            'lost': 'bg-red-100 text-red-800',
            'on_hold': 'bg-gray-100 text-gray-800',
        }
        return colors.get(self.status, 'bg-gray-100 text-gray-800')


class LeadActivity(models.Model):
    """
    Track all interactions and activities with investment leads.
    Provides full audit trail and timeline of engagement.
    """
    
    ACTIVITY_TYPES = [
        ('email', 'Email'),
        ('call', 'Phone Call'),
        ('meeting', 'Meeting'),
        ('note', 'Note'),
        ('status_change', 'Status Change'),
        ('document_sent', 'Document Sent'),
        ('follow_up', 'Follow-up'),
    ]
    
    OUTCOME_CHOICES = [
        ('positive', 'Positive'),
        ('neutral', 'Neutral'),
        ('negative', 'Negative'),
        ('no_response', 'No Response'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(
        InvestmentLead,
        on_delete=models.CASCADE,
        related_name='activities'
    )
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    subject = models.CharField(max_length=255)
    description = models.TextField()
    outcome = models.CharField(
        max_length=20,
        choices=OUTCOME_CHOICES,
        blank=True,
        help_text="Outcome of the activity"
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='investment_activities'
    )
    performed_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        verbose_name = 'Lead Activity'
        verbose_name_plural = 'Lead Activities'
        ordering = ['-performed_at']
        indexes = [
            models.Index(fields=['lead', '-performed_at']),
        ]
    
    def __str__(self):
        return f"{self.get_activity_type_display()} - {self.lead.full_name} ({self.performed_at.strftime('%Y-%m-%d %H:%M')})"
    
    def get_activity_icon(self):
        """Return icon class for activity type"""
        icons = {
            'email': 'mail',
            'call': 'phone',
            'meeting': 'event',
            'note': 'note',
            'status_change': 'swap_horiz',
            'document_sent': 'description',
            'follow_up': 'notification_important',
        }
        return icons.get(self.activity_type, 'circle')


class LeadNote(models.Model):
    """
    Quick notes and annotations for investment leads.
    Supports pinning important notes.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(
        InvestmentLead,
        on_delete=models.CASCADE,
        related_name='notes'
    )
    note = models.TextField()
    is_pinned = models.BooleanField(
        default=False,
        help_text="Pin this note to the top"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='investment_notes'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Lead Note'
        verbose_name_plural = 'Lead Notes'
        ordering = ['-is_pinned', '-created_at']
    
    def __str__(self):
        pinned_marker = "📌 " if self.is_pinned else ""
        return f"{pinned_marker}{self.note[:50]}... - {self.lead.full_name}"
