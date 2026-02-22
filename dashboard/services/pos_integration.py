"""
POS Integration Service
Handles linking CRM tenants to POS businesses and configuring webhooks

Location: dashboard/services/pos_integration.py
"""

import requests
import jwt
import logging
from typing import Dict, Optional
from django.conf import settings

logger = logging.getLogger(__name__)


class POSIntegrationService:
    """Service for integrating with POS system"""

    @staticmethod
    def _generate_auth_token() -> str:
        """Generate JWT token for POS API authentication"""
        secret = getattr(settings, 'INTEGRATION_SECRET', None)
        if not secret:
            raise ValueError("INTEGRATION_SECRET not configured")
        
        import time
        payload = {
            'iss': 'ayende-crm',
            'scope': 'integration',
            'iat': int(time.time()),
            'exp': int(time.time()) + 300  # 5 minutes
        }
        return jwt.encode(payload, secret, algorithm='HS256')

    @staticmethod
    def link_business_to_crm(pos_business_id: str, crm_tenant_uuid: str, subdomain: str) -> Dict:
        """
        Link a POS business to a CRM tenant by updating externalTenantId
        
        Args:
            pos_business_id: UUID of business in POS database
            crm_tenant_uuid: UUID of tenant in CRM database
            subdomain: Business subdomain
            
        Returns:
            Dict with success status and details
        """
        try:
            base_url = getattr(settings, 'POS_BASE_URL', None)
            if not base_url:
                return {
                    'success': False,
                    'error': 'POS_BASE_URL not configured'
                }
            
            # POS API endpoint to update business
            url = f"{base_url.rstrip('/')}/api/v1/businesses/{pos_business_id}/link-crm"
            
            # Generate auth token
            token = POSIntegrationService._generate_auth_token()
            
            # Prepare payload
            payload = {
                'externalTenantId': str(crm_tenant_uuid),
                'crmSubdomain': subdomain,
                'crmUrl': f'https://{subdomain}.ayendecx.com'
            }
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {token}'
            }
            
            logger.info(f"Linking POS business {pos_business_id} to CRM tenant {crm_tenant_uuid}")
            
            response = requests.patch(
                url,
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"Successfully linked POS business to CRM tenant")
                return {
                    'success': True,
                    'status_code': response.status_code,
                    'message': 'Business linked to CRM successfully'
                }
            else:
                logger.warning(f"Failed to link business: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'status_code': response.status_code,
                    'error': response.text
                }
                
        except requests.exceptions.Timeout:
            logger.error("POS API timeout when linking business")
            return {
                'success': False,
                'error': 'POS API timeout'
            }
        except requests.exceptions.ConnectionError as e:
            logger.error(f"POS API connection error: {str(e)}")
            return {
                'success': False,
                'error': f'Connection error: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Error linking business to CRM: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    @staticmethod
    def get_business_by_subdomain(subdomain: str) -> Optional[Dict]:
        """
        Get POS business details by subdomain
        
        Args:
            subdomain: Business subdomain
            
        Returns:
            Business data or None if not found
        """
        try:
            base_url = getattr(settings, 'POS_BASE_URL', None)
            if not base_url:
                return None
            
            url = f"{base_url.rstrip('/')}/api/v1/businesses/by-subdomain/{subdomain}"
            
            token = POSIntegrationService._generate_auth_token()
            headers = {'Authorization': f'Bearer {token}'}
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Business not found: {subdomain}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching business: {str(e)}")
            return None

    @staticmethod
    def test_webhook_connection(tenant_uuid: str, subdomain: str) -> Dict:
        """
        Test webhook connection by sending a test ping
        
        Args:
            tenant_uuid: CRM tenant UUID
            subdomain: Business subdomain
            
        Returns:
            Test results
        """
        try:
            base_url = getattr(settings, 'POS_BASE_URL', None)
            if not base_url:
                return {'success': False, 'error': 'POS_BASE_URL not configured'}
            
            url = f"{base_url.rstrip('/')}/api/v1/webhooks/test"
            
            token = POSIntegrationService._generate_auth_token()
            
            payload = {
                'tenantId': str(tenant_uuid),
                'subdomain': subdomain,
                'source': 'crm-provisioning'
            }
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {token}'
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            return {
                'success': response.status_code == 200,
                'status_code': response.status_code,
                'message': response.json() if response.status_code == 200 else response.text
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
