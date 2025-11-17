# dashboard/services/webhook_service.py
"""
Webhook service for sending customer data to POS system.
Handles webhook signing, retry logic, and error handling.

UPDATED: Fixed to use TenantCustomer name fields instead of global Customer
CRITICAL FIX: When editing in CRM UI, TenantCustomer gets updated, not Customer!
Therefore webhook must send TenantCustomer.first_name/last_name, not Customer.first_name/last_name
"""

import requests
import json
import hmac
import hashlib
import time
import jwt
from django.conf import settings
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class WebhookService:
    """Service for sending webhooks to POS system"""
    
    @staticmethod
    def _get_tenant_id(tenant) -> str:
        """
        Get tenant ID in a way that works with any primary key field name.
        
        Args:
            tenant: Tenant instance
            
        Returns:
            String representation of tenant primary key
        """
        # Try different possible field names
        if hasattr(tenant, 'tenant_uuid'):
            return str(tenant.tenant_uuid)
        elif hasattr(tenant, 'uuid'):
            return str(tenant.uuid)
        elif hasattr(tenant, 'id'):
            return str(tenant.id)
        else:
            # Fall back to pk which always works
            return str(tenant.pk)
    
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
        # Try to get URL from tenant settings first
        base_url = None
        if hasattr(tenant, 'settings') and isinstance(tenant.settings, dict):
            base_url = tenant.settings.get('pos_webhook_url')
        
        # Fall back to global setting
        if not base_url:
            base_url = getattr(settings, 'POS_BASE_URL', None)
            
        if not base_url:
            logger.warning("POS_BASE_URL not configured in settings")
            return None
        
        # All operations use the same endpoint
        endpoint = '/api/v1/webhooks/customer'
        
        return f"{base_url.rstrip('/')}{endpoint}"
    
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
    def _prepare_customer_payload(customer, tenant_customer, operation: str, tenant) -> Dict:
        """
        Prepare customer data for webhook payload.
        
        CRITICAL FIX: Uses TenantCustomer fields for name (not Customer)
        because CRM UI edits TenantCustomer, not Customer!
        
        Args:
            customer: Customer model instance (global identity)
            tenant_customer: TenantCustomer model instance (tenant-specific data)
            operation: 'created', 'updated', or 'deleted'
            tenant: Tenant instance
            
        Returns:
            Dictionary with customer data
        """
        # Get tenant ID using helper method
        tenant_id = WebhookService._get_tenant_id(tenant)
        
        # For delete operations, send minimal data
        if operation == 'deleted':
            external_id = None
            if tenant_customer and tenant_customer.external_id:
                external_id = str(tenant_customer.external_id)
                
            return {
                'operation': operation,
                'customerId': str(customer.id),  # CRM customer ID (global)
                'externalId': external_id,  # POS customer ID (if exists)
                'tenantId': tenant_id,
                'timestamp': int(time.time())
            }
        
        # For create/update, send full customer data
        # Note: tenant_customer might be None for new customers
        if not tenant_customer:
            logger.warning(f"No TenantCustomer found for customer {customer.id} in tenant {tenant_id}")
            
        return {
            'operation': operation,
            'customerId': str(customer.id),  # CRM customer ID (global identity)
            'externalId': str(tenant_customer.external_id) if tenant_customer and tenant_customer.external_id else None,
            
            # CRITICAL FIX: Use TenantCustomer name fields, NOT Customer fields!
            # When user edits customer in CRM UI, they're editing TenantCustomer
            # Global Customer remains unchanged
            'firstName': tenant_customer.first_name if tenant_customer else customer.first_name,
            'lastName': tenant_customer.last_name if tenant_customer else customer.last_name,
            
            # Contact info from TenantCustomer (tenant-specific)
            'email': tenant_customer.email if tenant_customer else '',
            'phone': tenant_customer.phone if tenant_customer else '',
            
            # Address from TenantCustomer
            'address': tenant_customer.address if tenant_customer else '',
            'city': tenant_customer.city if tenant_customer else '',
            'state': tenant_customer.state if tenant_customer else '',
            'postalCode': tenant_customer.zip_code if tenant_customer else '',
            
            # Personal details from TenantCustomer
            'dateOfBirth': tenant_customer.date_of_birth.isoformat() if tenant_customer and tenant_customer.date_of_birth else None,
            'marketingOptIn': tenant_customer.marketing_opt_in if tenant_customer else False,
            
            # Loyalty data from TenantCustomer
            'loyaltyPoints': int(tenant_customer.loyalty_points) if tenant_customer else 0,
            'loyaltyTier': tenant_customer.loyalty_tier if tenant_customer else 'BRONZE',
            'totalSpent': float(tenant_customer.total_spent) if tenant_customer else 0.0,
            'visitCount': tenant_customer.visit_count if tenant_customer else 0,
            
            # Tenant identification
            'tenantId': tenant_id,
            'timestamp': int(time.time())
        }
    
    @staticmethod
    def _send_webhook(url: str, payload: Dict, secret: str, max_retries: int = 3) -> Dict:
        """
        Send webhook with retry logic.
        
        Args:
            url: Webhook URL
            payload: Payload dictionary
            secret: Secret for signing
            max_retries: Maximum number of retry attempts
            
        Returns:
            Dictionary with success status and any POS customer ID returned
        """
        payload_json = json.dumps(payload, separators=(',', ':'))
        
        # Generate JWT token for authentication
        token_payload = {
            'iss': 'ayende-crm',
            'scope': 'webhook',
            'tenant_id': payload.get('tenantId'),
            'iat': int(time.time()),
            'exp': int(time.time()) + 300  # 5 minute expiry (short-lived)
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
                    
                    # Try to extract POS customer ID from response
                    try:
                        response_data = response.json()
                        pos_customer_id = None
                        
                        if response_data.get('success') and response_data.get('customer'):
                            pos_customer_id = response_data['customer'].get('id')
                            
                        return {
                            'success': True,
                            'status_code': response.status_code,
                            'pos_customer_id': pos_customer_id
                        }
                    except:
                        return {
                            'success': True,
                            'status_code': response.status_code,
                            'pos_customer_id': None
                        }
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
        return {
            'success': False,
            'status_code': None,
            'pos_customer_id': None
        }
    
    @classmethod
    def send_customer_webhook(cls, customer, operation: str, tenant, tenant_customer=None) -> bool:
        """
        Send customer webhook to POS system.
        
        Args:
            customer: Customer model instance (global identity)
            operation: 'created', 'updated', or 'deleted'
            tenant: Tenant object
            
        Returns:
            True if webhook sent successfully, False otherwise
        """
        try:
            # Check if integration is enabled
            if not getattr(settings, 'ENABLE_CRM_SYNC', False):
                logger.debug(f"CRM sync disabled, skipping webhook for customer {customer.id}")
                return False
            
            # Get webhook URL
            webhook_url = cls._get_webhook_url(tenant, operation)
            if not webhook_url:
                logger.error("Webhook URL not configured")
                return False
            
            # Get secret key
            secret = getattr(settings, 'INTEGRATION_SECRET', None)
            if not secret:
                logger.error("INTEGRATION_SECRET not configured")
                return False
            
            # Get tenant ID for logging
            tenant_id = cls._get_tenant_id(tenant)
            
            # Get TenantCustomer for this tenant (use provided one if available)
            if not tenant_customer:
                tenant_customer = customer.tenant_accounts.filter(tenant=tenant).first()
            
            if not tenant_customer and operation != 'deleted':
                logger.warning(
                    f"No TenantCustomer found for customer {customer.id} in tenant {tenant_id}"
                )
                # Still send webhook for created operation (might be during registration)
                if operation != 'created':
                    return False
            
            # Get subdomain for logging if available
            subdomain = getattr(tenant, 'subdomain', tenant_id)
            
            logger.info(
                f"Sending {operation} webhook for customer {customer.id} "
                f"({customer.first_name} {customer.last_name}) to tenant {subdomain}"
            )
            
            # Prepare payload
            payload = cls._prepare_customer_payload(customer, tenant_customer, operation, tenant)
            
            # Send webhook
            result = cls._send_webhook(webhook_url, payload, secret)
            
            # If webhook successful and this was a creation, update external_id
            if result['success'] and operation == 'created' and result['pos_customer_id']:
                pos_customer_id = result['pos_customer_id']
                
                # Update TenantCustomer with POS customer ID
                if tenant_customer and not tenant_customer.external_id:
                    tenant_customer.external_id = pos_customer_id
                    tenant_customer.save(update_fields=['external_id'])
                    logger.info(f"Updated external_id to: {pos_customer_id}")
            
            return result['success']
            
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
            base_url = getattr(settings, 'POS_BASE_URL', None)
            if not base_url:
                return {
                    'success': False,
                    'error': 'POS_BASE_URL not configured'
                }
            
            # Try to ping the health check endpoint
            health_url = f"{base_url.rstrip('/')}/api/v1/webhooks/health"
            
            logger.info(f"Testing webhook connection to: {health_url}")
            
            response = requests.get(health_url, timeout=5)
            
            return {
                'success': response.status_code == 200,
                'status_code': response.status_code,
                'url': base_url,
                'message': response.json() if response.status_code == 200 else response.text
            }
            
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'Connection timeout'
            }
        except requests.exceptions.ConnectionError as e:
            return {
                'success': False,
                'error': f'Connection error: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }