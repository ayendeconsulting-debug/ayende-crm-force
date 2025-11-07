# dashboard/services/webhook_service.py
"""
Webhook service for sending customer data to POS system.
Handles webhook signing, retry logic, and error handling.

FIXED:
- Line 211: Changed MappingService.get_external_id() to MappingService.get_business_id()
- Removed incorrect import: from .models import Customer
"""

import requests
import json
import hmac
import hashlib
import time
from django.conf import settings
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class WebhookService:
    """Service for sending webhooks to POS system"""
    
    @staticmethod
    def _get_webhook_url(tenant, operation: str) -> Optional[str]:
        """
        Get the webhook URL for a specific operation.
        
        Args:
            tenant: The tenant object
            operation: 'created', 'updated', or 'deleted'
            
        Returns:
            Full webhook URL or None if not configured
        """
        base_url = getattr(settings, 'POS_WEBHOOK_URL', None)
        if not base_url:
            logger.warning("POS_WEBHOOK_URL not configured in settings")
            return None
        
        # Map operations to endpoints
        endpoint_map = {
            'created': '/api/v1/webhooks/customer',
            'updated': '/api/v1/webhooks/customer',
            'deleted': '/api/v1/webhooks/customer'
        }
        
        endpoint = endpoint_map.get(operation)
        if not endpoint:
            logger.error(f"Unknown operation: {operation}")
            return None
        
        return f"{base_url}{endpoint}"
    
    @staticmethod
    def _generate_signature(payload: str, secret: str) -> str:
        """
        Generate HMAC signature for webhook payload.
        
        Args:
            payload: JSON string of the payload
            secret: Secret key for signing
            
        Returns:
            Hex digest of HMAC signature
        """
        return hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    @staticmethod
    def _prepare_customer_payload(customer, operation: str) -> Dict:
        """
        Prepare customer data for webhook payload.
        
        Args:
            customer: Customer model instance
            operation: 'created', 'updated', or 'deleted'
            
        Returns:
            Dictionary with customer data
        """
        # Get tenant for tenant_id
        tenant = customer.tenants.first()
        tenant_uuid = str(tenant.tenant_uuid) if tenant else None
        
        # For delete operations, send minimal data
        if operation == 'deleted':
            return {
                'operation': operation,
                'customerId': str(customer.id),
                'tenantId': tenant_uuid,
                'timestamp': int(time.time())
            }
        
        # For create/update, send full customer data
        return {
            'operation': operation,
            'customerId': str(customer.id),
            'externalId': str(customer.id),  # POS customer ID (same as CRM ID for now)
            'email': customer.email or '',
            'firstName': customer.first_name,
            'lastName': customer.last_name,
            'phone': customer.phone or '',
            'dateOfBirth': customer.date_of_birth.isoformat() if customer.date_of_birth else None,
            'address': customer.address or '',
            'city': customer.city or '',
            'state': customer.state or '',
            'postalCode': customer.postal_code or '',
            'loyaltyPoints': customer.loyalty_points or 0,
            'loyaltyTier': customer.loyalty_tier or 'BRONZE',
            'totalSpent': float(customer.total_spent or 0),
            'visitCount': customer.visit_count or 0,
            'marketingOptIn': customer.marketing_opt_in or False,
            'tenantId': tenant_uuid,
            'timestamp': int(time.time())
        }
    
    @staticmethod
    def _send_webhook(url: str, payload: Dict, secret: str, max_retries: int = 3) -> bool:
        """
        Send webhook with retry logic.
        
        Args:
            url: Webhook URL
            payload: Payload dictionary
            secret: Secret for signing
            max_retries: Maximum number of retry attempts
            
        Returns:
            True if successful, False otherwise
        """
        payload_json = json.dumps(payload, separators=(',', ':'))
        
        # Generate JWT token for authentication
        import jwt
        token_payload = {
            'iss': 'ayende-crm',
            'scope': 'webhook',
            'iat': int(time.time()),
            'exp': int(time.time()) + 3600  # 1 hour expiry
        }
        token = jwt.encode(token_payload, secret, algorithm='HS256')
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}',
            'X-Tenant-ID': payload.get('tenantId', ''),
            'User-Agent': 'Ayende-CRM-Webhook/1.0'
        }
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Sending webhook to {url} (attempt {attempt + 1}/{max_retries})")
                
                response = requests.post(
                    url,
                    data=payload_json,
                    headers=headers,
                    timeout=10  # 10 second timeout
                )
                
                if response.status_code in [200, 201, 204]:
                    logger.info(f"Webhook sent successfully: {response.status_code}")
                    return True
                else:
                    logger.warning(
                        f"Webhook failed with status {response.status_code}: {response.text}"
                    )
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Webhook timeout (attempt {attempt + 1}/{max_retries})")
                
            except requests.exceptions.ConnectionError:
                logger.warning(f"Webhook connection error (attempt {attempt + 1}/{max_retries})")
                
            except Exception as e:
                logger.error(f"Webhook error: {str(e)}", exc_info=True)
            
            # Wait before retry (exponential backoff)
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                logger.info(f"Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
        
        logger.error(f"Webhook failed after {max_retries} attempts")
        return False
    
    @classmethod
    def send_customer_webhook(cls, customer, operation: str, tenant) -> bool:
        """
        Send customer webhook to POS system.
        
        Args:
            customer: Customer model instance
            operation: 'created', 'updated', or 'deleted'
            tenant: Tenant object
            
        Returns:
            True if webhook sent successfully, False otherwise
        """
        try:
            # Get webhook URL
            webhook_url = cls._get_webhook_url(tenant, operation)
            if not webhook_url:
                return False
            
            # Get secret key
            secret = getattr(settings, 'INTEGRATION_SECRET', None)
            if not secret:
                logger.error("INTEGRATION_SECRET not configured")
                return False
            
            logger.info(
                f"Sending {operation} webhook for customer {customer.id} "
                f"({customer.first_name} {customer.last_name})"
            )
            
            # Prepare payload
            payload = cls._prepare_customer_payload(customer, operation)
            
            # Send webhook
            return cls._send_webhook(webhook_url, payload, secret)
            
        except Exception as e:
            logger.error(
                f"Failed to send customer webhook: {str(e)}",
                exc_info=True
            )
            return False
    
    @classmethod
    def test_webhook_connection(cls, tenant) -> Dict:
        """
        Test webhook connection to POS system.
        
        Args:
            tenant: Tenant object
            
        Returns:
            Dictionary with test results
        """
        try:
            base_url = getattr(settings, 'POS_WEBHOOK_URL', None)
            if not base_url:
                return {
                    'success': False,
                    'error': 'POS_WEBHOOK_URL not configured'
                }
            
            # Try to ping the health check endpoint
            health_url = f"{base_url}/api/v1/webhooks/health"
            
            response = requests.get(health_url, timeout=5)
            
            return {
                'success': response.status_code == 200,
                'status_code': response.status_code,
                'url': base_url
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }