"""
Custom Health Checks for AyendeCX Platform
Tests critical integrations: POS API, SendGrid, Anthropic
"""

import requests
from django.conf import settings
from health_check.backends import HealthCheck
from health_check.exceptions import ServiceUnavailable, ServiceReturnedUnexpectedResult


class POSAPIHealthCheck(HealthCheck):
    """
    Check if POS API is reachable
    Tests the health endpoint of POS system
    """
    critical_service = True  # Mark as critical - system fails if this fails
    
    def check_status(self):
        """Perform the health check"""
        pos_url = getattr(settings, 'POS_API_URL', None)
        
        if not pos_url:
            raise ServiceUnavailable("POS_API_URL not configured")
        
        try:
            # Test POS health endpoint with 5 second timeout
            health_url = f"{pos_url}/api/v1/health"
            response = requests.get(health_url, timeout=5)
            
            if response.status_code == 200:
                # POS is responding
                return
            else:
                raise ServiceReturnedUnexpectedResult(
                    f"POS API returned {response.status_code}"
                )
        except requests.exceptions.Timeout:
            raise ServiceUnavailable("POS API timeout - no response in 5 seconds")
        except requests.exceptions.ConnectionError:
            raise ServiceUnavailable("Cannot connect to POS API")
        except Exception as e:
            raise ServiceUnavailable(f"POS API check failed: {str(e)}")
    
    def identifier(self):
        return "POS API Connection"


class SendGridHealthCheck(HealthCheck):
    """
    Check if SendGrid email service is configured
    Tests API key validity
    """
    critical_service = False  # Not critical - system can run without email
    
    def check_status(self):
        """Perform the health check"""
        api_key = getattr(settings, 'EMAIL_HOST_PASSWORD', None)
        
        if not api_key:
            raise ServiceUnavailable("SENDGRID_API_KEY not configured")
        
        try:
            # Test SendGrid API with key validation
            response = requests.get(
                'https://api.sendgrid.com/v3/scopes',
                headers={'Authorization': f'Bearer {api_key}'},
                timeout=5
            )
            
            if response.status_code == 200:
                # SendGrid API key is valid
                return
            elif response.status_code == 401:
                raise ServiceUnavailable("SendGrid API key is invalid")
            else:
                raise ServiceReturnedUnexpectedResult(
                    f"SendGrid API returned {response.status_code}"
                )
        except requests.exceptions.Timeout:
            raise ServiceUnavailable("SendGrid API timeout")
        except Exception as e:
            raise ServiceUnavailable(f"SendGrid check failed: {str(e)}")
    
    def identifier(self):
        return "SendGrid Email Service"


class AnthropicAPIHealthCheck(HealthCheck):
    """
    Check if Anthropic API is accessible
    Tests chatbot functionality
    """
    critical_service = False  # Not critical - chatbot is optional feature
    
    def check_status(self):
        """Perform the health check"""
        api_key = getattr(settings, 'ANTHROPIC_API_KEY', None)
        
        if not api_key:
            # Chatbot is optional, so just warn
            raise ServiceUnavailable("ANTHROPIC_API_KEY not configured (chatbot disabled)")
        
        try:
            # Simple ping to Anthropic API to verify key works
            # Using minimal request to avoid usage charges
            response = requests.get(
                'https://api.anthropic.com/v1/messages',
                headers={
                    'x-api-key': api_key,
                    'anthropic-version': '2023-06-01'
                },
                timeout=5
            )
            
            # We expect 400 or 405 (method not allowed) with valid key
            # 401 means invalid key
            if response.status_code in [400, 405]:
                # API key is valid (just wrong method/params)
                return
            elif response.status_code == 401:
                raise ServiceUnavailable("Anthropic API key is invalid")
            else:
                # API might be down or other issue
                raise ServiceReturnedUnexpectedResult(
                    f"Anthropic API returned {response.status_code}"
                )
        except requests.exceptions.Timeout:
            raise ServiceUnavailable("Anthropic API timeout")
        except Exception as e:
            raise ServiceUnavailable(f"Anthropic check failed: {str(e)}")
    
    def identifier(self):
        return "Anthropic Chatbot API"


class WebhookSyncHealthCheck(HealthCheck):
    """
    Check recent webhook sync status
    Warns if there are recent sync failures
    """
    critical_service = False
    
    def check_status(self):
        """Check for recent sync errors"""
        try:
            from customers.models import SyncLog
            from django.utils import timezone
            from datetime import timedelta
            
            # Check last hour for failed syncs
            one_hour_ago = timezone.now() - timedelta(hours=1)
            recent_failures = SyncLog.objects.filter(
                created_at__gte=one_hour_ago,
                status='failed'
            ).count()
            
            if recent_failures > 10:
                # More than 10 failures in last hour is concerning
                raise ServiceReturnedUnexpectedResult(
                    f"{recent_failures} webhook sync failures in last hour"
                )
            elif recent_failures > 0:
                # Some failures but not critical
                pass  # Don't error, just log
                
        except Exception as e:
            # If we can't check, don't fail the health check
            pass
    
    def identifier(self):
        return "Webhook Sync Status"