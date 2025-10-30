# dashboard/services/webhook_service.py
"""
Webhook service for sending customer data to POS system.
Handles webhook signing, retry logic, and error handling.

FIXED:
- Line 211: Changed MappingService.get_external_id() to MappingService.get_business_id()
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
            'created': '/api/integration/webhook/customer-created',
            'updated': '/api/integration/webhook/customer-updated',
            'deleted': '/api/integration/webhook/customer-deleted'
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
        tenant_uuid = tenant.tenant_uuid if tenant else None
        
        # For delete operations, send minimal data
        if operation == 'deleted':
            return {
                'operation': operation,
                'customer_id': str(customer.id),
                'tenant_id': tenant_uuid,
                'timestamp': int(time.time())
            }
        
        # For create/update, send full customer data
        return {
            'operation': operation,
            'customer': {
                'id': str(customer.id),
                'first_name': customer.first_name,
                'last_name': customer.last_name,
                'email': customer.email or '',
                'phone': customer.phone or '',
                'date_of_birth': customer.date_of_birth.isoformat() if customer.date_of_birth else None,
                'address': customer.address or '',
                'city': customer.city or '',
                'state': customer.state or '',
                'zip_code': customer.postal_code or '',
                'loyalty_points': customer.loyalty_points or 0,
                'loyalty_tier': customer.loyalty_tier or 'BRONZE',
                'total_spent': float(customer.total_spent or 0),
                'visit_count': customer.visit_count or 0,
                'marketing_opt_in': customer.marketing_opt_in or False,
                'notes': customer.notes or '',
                'is_active': customer.is_active,
                'created_at': customer.created_at.isoformat() if customer.created_at else None,
                'updated_at': customer.updated_at.isoformat() if customer.updated_at else None,
            },
            'tenant_id': tenant_uuid,
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
        signature = WebhookService._generate_signature(payload_json, secret)
        
        headers = {
            'Content-Type': 'application/json',
            'X-Webhook-Signature': signature,
            'X-Tenant-ID': payload.get('tenant_id', ''),
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
            
            # Check if we should send webhooks for this tenant
            # (based on system mapping)
            from dashboard.services.mapping_service import MappingService
            
            # Get POS business ID for this tenant
            # FIXED: Changed from get_external_id() to get_business_id()
            pos_business = MappingService.get_business_id(tenant.tenant_uuid)
            
            if not pos_business:
                logger.warning(
                    f"No POS business mapping found for tenant {tenant.tenant_uuid}, "
                    "skipping webhook"
                )
                # Don't fail - just skip webhook if no mapping exists yet
                return True
            
            logger.info(
                f"Sending {operation} webhook for customer {customer.id} "
                f"to POS business {pos_business}"
            )
            
            # Prepare payload
            payload = cls._prepare_customer_payload(customer, operation)
            payload['pos_business_id'] = pos_business  # Add POS business context
            
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
            health_url = f"{base_url}/api/health"
            
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
