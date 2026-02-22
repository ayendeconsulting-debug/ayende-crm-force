"""
Custom Health Checks for AyendeCX Platform
Tests critical integrations: POS API, SendGrid, Anthropic

Location: dashboard/health_checks.py
"""

import requests
from django.conf import settings
from health_check.backends import HealthCheck
from health_check.exceptions import ServiceUnavailable, ServiceReturnedUnexpectedResult
from health_check.plugins import plugin_dir


class POSAPIHealthCheck(HealthCheck):
    """Check if POS API is reachable"""
    
    def check_status(self):
        pos_url = getattr(settings, 'POS_API_URL', None)
        if not pos_url:
            raise ServiceUnavailable("POS_API_URL not configured")
        
        try:
            health_url = f"{pos_url}/api/v1/health"
            response = requests.get(health_url, timeout=5)
            
            if response.status_code != 200:
                raise ServiceReturnedUnexpectedResult(f"POS API returned {response.status_code}")
        except requests.exceptions.Timeout:
            raise ServiceUnavailable("POS API timeout")
        except requests.exceptions.ConnectionError:
            raise ServiceUnavailable("Cannot connect to POS API")
        except Exception as e:
            raise ServiceUnavailable(f"POS API check failed: {str(e)}")
    
    def identifier(self):
        return "POS API Connection"


class SendGridHealthCheck(HealthCheck):
    """Check if SendGrid email service is configured"""
    
    def check_status(self):
        api_key = getattr(settings, 'EMAIL_HOST_PASSWORD', None)
        if not api_key:
            raise ServiceUnavailable("SendGrid API key not configured")
        
        try:
            response = requests.get(
                'https://api.sendgrid.com/v3/scopes',
                headers={'Authorization': f'Bearer {api_key}'},
                timeout=5
            )
            
            if response.status_code == 401:
                raise ServiceUnavailable("SendGrid API key is invalid")
            elif response.status_code != 200:
                raise ServiceReturnedUnexpectedResult(f"SendGrid returned {response.status_code}")
        except requests.exceptions.Timeout:
            raise ServiceUnavailable("SendGrid API timeout")
        except Exception as e:
            raise ServiceUnavailable(f"SendGrid check failed: {str(e)}")
    
    def identifier(self):
        return "SendGrid Email Service"


class AnthropicAPIHealthCheck(HealthCheck):
    """Check if Anthropic API is accessible"""
    
    def check_status(self):
        api_key = getattr(settings, 'ANTHROPIC_API_KEY', None)
        if not api_key:
            raise ServiceUnavailable("Anthropic API key not configured (chatbot disabled)")
        
        try:
            response = requests.get(
                'https://api.anthropic.com/v1/messages',
                headers={'x-api-key': api_key, 'anthropic-version': '2023-06-01'},
                timeout=5
            )
            
            # 400/405 = valid key, wrong method | 401 = invalid key
            if response.status_code == 401:
                raise ServiceUnavailable("Anthropic API key is invalid")
            elif response.status_code not in [400, 405]:
                raise ServiceReturnedUnexpectedResult(f"Anthropic returned {response.status_code}")
        except requests.exceptions.Timeout:
            raise ServiceUnavailable("Anthropic API timeout")
        except Exception as e:
            raise ServiceUnavailable(f"Anthropic check failed: {str(e)}")
    
    def identifier(self):
        return "Anthropic Chatbot API"


class WebhookSyncHealthCheck(HealthCheck):
    """Check recent webhook sync status"""
    
    def check_status(self):
        try:
            from customers.models import SyncLog
            from django.utils import timezone
            from datetime import timedelta
            
            one_hour_ago = timezone.now() - timedelta(hours=1)
            recent_failures = SyncLog.objects.filter(
                created_at__gte=one_hour_ago,
                status='failed'
            ).count()
            
            if recent_failures > 10:
                raise ServiceReturnedUnexpectedResult(
                    f"{recent_failures} webhook failures in last hour"
                )
        except Exception:
            pass  # Don't fail if we can't check
    
    def identifier(self):
        return "Webhook Sync Status"


# Auto-register all health checks when Django loads this app
plugin_dir.register(POSAPIHealthCheck)
plugin_dir.register(SendGridHealthCheck)
plugin_dir.register(AnthropicAPIHealthCheck)
plugin_dir.register(WebhookSyncHealthCheck)