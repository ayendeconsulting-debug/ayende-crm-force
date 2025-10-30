"""
Integration Authentication
JWT token validation for POS-CRM integration
"""

import jwt
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.conf import settings


class IntegrationJWTAuthentication(BaseAuthentication):
    """
    Custom authentication for system-to-system integration.
    Validates JWT tokens issued by POS system.
    """
    
    def authenticate(self, request):
        """
        Authenticate the request and return a two-tuple of (user, token_payload).
        
        Since this is system-to-system, we return None for user and the
        decoded token payload.
        """
        
        # Get Authorization header
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            return None  # Let other authentication classes handle it
        
        token = auth_header.replace('Bearer ', '')
        
        try:
            # Get integration secret from settings
            secret = getattr(settings, 'INTEGRATION_SECRET', None)
            
            if not secret:
                raise AuthenticationFailed('Integration secret not configured')
            
            # Decode and verify JWT token
            payload = jwt.decode(
                token,
                secret,
                algorithms=['HS256']
            )
            
            # Validate issuer
            if payload.get('iss') != 'ayende-pos':
                raise AuthenticationFailed('Invalid token issuer')
            
            # Validate scope
            if payload.get('scope') != 'integration':
                raise AuthenticationFailed('Invalid token scope')
            
            # Validate tenant ID
            tenant_id = payload.get('tenantId')
            if not tenant_id:
                raise AuthenticationFailed('Tenant ID missing in token')
            
            # Store token payload in request for later use
            request.integration_token = payload
            request.integration_tenant_id = tenant_id
            
            # Return None for user (system-to-system auth)
            # and the payload as auth object
            return (None, payload)
            
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed('Integration token has expired')
        
        except jwt.InvalidTokenError as e:
            raise AuthenticationFailed(f'Invalid integration token: {str(e)}')
        
        except Exception as e:
            raise AuthenticationFailed(f'Authentication error: {str(e)}')
    
    def authenticate_header(self, request):
        """
        Return a string to be used as the value of the WWW-Authenticate
        header in a 401 Unauthenticated response.
        """
        return 'Bearer realm="Integration API"'


class IntegrationPermission:
    """
    Permission class to validate tenant access in integration requests.
    """
    
    def has_permission(self, request, view):
        """
        Check if request has valid integration authentication and tenant access.
        """
        
        # Check if integration token was validated
        if not hasattr(request, 'integration_tenant_id'):
            return False
        
        # Validate tenant ID header matches token
        tenant_id_header = request.headers.get('X-Tenant-ID')
        
        if not tenant_id_header:
            return False
        
        if tenant_id_header != request.integration_tenant_id:
            return False
        
        return True
