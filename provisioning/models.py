"""
Provisioning Models
Handles CRM tenant provisioning from POS registrations

Location: provisioning/models.py
"""

import uuid
import hashlib
import hmac
import json
import base64
from datetime import timedelta
from django.db import models
from django.conf import settings
from django.utils import timezone
from tenants.models import Tenant


class ProvisioningToken(models.Model):
    """
    Stores provisioning requests from POS system.
    Tracks pending, completed, and expired provisions.
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('expired', 'Expired'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Token data
    token = models.CharField(max_length=500, unique=True, db_index=True)
    signature = models.CharField(max_length=255)
    
    # Business data from POS
    business_name = models.CharField(max_length=255)
    subdomain = models.CharField(max_length=100)
    business_email = models.EmailField()
    business_phone = models.CharField(max_length=50, blank=True, null=True)
    
    # Owner data
    owner_first_name = models.CharField(max_length=100)
    owner_last_name = models.CharField(max_length=100)
    owner_email = models.EmailField()
    
    # Branding
    primary_color = models.CharField(max_length=20, default='#667eea')
    secondary_color = models.CharField(max_length=20, default='#764ba2')
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Related tenant (after provisioning)
    tenant = models.ForeignKey(
        Tenant, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='provisioning_tokens'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    provisioned_at = models.DateTimeField(null=True, blank=True)
    provisioned_by = models.CharField(max_length=255, blank=True, null=True)
    
    # Error tracking
    error_message = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Provisioning Token'
        verbose_name_plural = 'Provisioning Tokens'
    
    def __str__(self):
        return f"{self.business_name} ({self.subdomain}) - {self.status}"
    
    @property
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    @property
    def is_valid(self):
        return self.status == 'pending' and not self.is_expired
    
    def mark_completed(self, tenant, admin_user):
        """Mark token as successfully provisioned"""
        self.status = 'completed'
        self.tenant = tenant
        self.provisioned_at = timezone.now()
        self.provisioned_by = admin_user
        self.save()
    
    def mark_failed(self, error_message):
        """Mark token as failed"""
        self.status = 'failed'
        self.error_message = error_message
        self.save()
    
    def mark_expired(self):
        """Mark token as expired"""
        self.status = 'expired'
        self.save()
    
    @classmethod
    def create_from_payload(cls, payload_data, token, signature):
        """Create a ProvisioningToken from validated payload"""
        expires_at = timezone.now() + timedelta(hours=72)
        
        return cls.objects.create(
            token=token,
            signature=signature,
            business_name=payload_data.get('businessName'),
            subdomain=payload_data.get('subdomain'),
            business_email=payload_data.get('businessEmail'),
            business_phone=payload_data.get('businessPhone'),
            owner_first_name=payload_data.get('ownerFirstName'),
            owner_last_name=payload_data.get('ownerLastName'),
            owner_email=payload_data.get('ownerEmail'),
            primary_color=payload_data.get('primaryColor', '#667eea'),
            secondary_color=payload_data.get('secondaryColor', '#764ba2'),
            expires_at=expires_at,
        )
    
    @staticmethod
    def verify_signature(payload_b64, signature):
        """Verify HMAC signature of payload"""
        secret = settings.PROVISIONING_SECRET_KEY
        if not secret:
            raise ValueError("PROVISIONING_SECRET_KEY not configured")
        
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload_b64.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)
    
    @staticmethod
    def decode_payload(payload_b64):
        """Decode base64 payload to dict"""
        try:
            payload_json = base64.urlsafe_b64decode(payload_b64.encode('utf-8')).decode('utf-8')
            return json.loads(payload_json)
        except Exception as e:
            raise ValueError(f"Invalid payload encoding: {str(e)}")


class SetupWizardProgress(models.Model):
    """Tracks business owner's progress through setup wizard"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Link to tenant
    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name='setup_progress'
    )
    
    # Setup token for wizard access
    setup_token = models.CharField(max_length=255, unique=True, db_index=True)
    setup_token_expires_at = models.DateTimeField()
    
    # Step completion status
    step_1_completed = models.BooleanField(default=False)  # Verify Details
    step_2_completed = models.BooleanField(default=False)  # Set Password
    step_3_completed = models.BooleanField(default=False)  # Configure Loyalty
    step_4_completed = models.BooleanField(default=False)  # Import Customers
    step_5_completed = models.BooleanField(default=False)  # Review & Complete
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Setup Wizard Progress'
        verbose_name_plural = 'Setup Wizard Progress'
    
    def __str__(self):
        return f"Setup: {self.tenant.name} - Step {self.current_step}/5"
    
    @property
    def current_step(self):
        """Return current step number (1-5)"""
        if not self.step_1_completed:
            return 1
        elif not self.step_2_completed:
            return 2
        elif not self.step_3_completed:
            return 3
        elif not self.step_4_completed:
            return 4
        elif not self.step_5_completed:
            return 5
        else:
            return 5
    
    @property
    def is_completed(self):
        return all([
            self.step_1_completed,
            self.step_2_completed,
            self.step_3_completed,
            self.step_4_completed,
            self.step_5_completed,
        ])
    
    @property
    def is_token_valid(self):
        return timezone.now() < self.setup_token_expires_at
    
    def complete_step(self, step_number):
        """Mark a step as completed"""
        step_field = f'step_{step_number}_completed'
        if hasattr(self, step_field):
            setattr(self, step_field, True)
            if self.is_completed:
                self.completed_at = timezone.now()
            self.save()
    
    @classmethod
    def create_for_tenant(cls, tenant):
        """Create setup wizard progress for a newly provisioned tenant"""
        import secrets
        
        setup_token = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timedelta(days=7)
        
        return cls.objects.create(
            tenant=tenant,
            setup_token=setup_token,
            setup_token_expires_at=expires_at,
        )