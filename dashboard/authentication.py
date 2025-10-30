"""
POS Integration Authentication
JWT-based authentication for system-to-system communication
"""

import jwt
from django.conf import settings
from rest_framework import authentication
from rest_framework import exceptions


class IntegrationJWTAuthentication(authentication.BaseAuthentication):
    """
    JWT authentication for POS system integration.
    Validates tokens from POS system for sync operations.
    """
    
    def authenticate(self, request):
        """
        Authenticate the request using JWT token from Authorization header.
        
        Returns:
            (None, payload) on success
            None if authentication fails
        """
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header:
            return None
        
        # Extract token from "Bearer <token>"
        try:
            token = auth_header.split(' ')[1] if ' ' in auth_header else auth_header
        except IndexError:
            raise exceptions.AuthenticationFailed('Invalid authorization header format')
        
        try:
            # Decode and validate JWT token
            payload = jwt.decode(
                token,
                settings.INTEGRATION_SECRET,
                algorithms=['HS256']
            )
            
            # Validate issuer
            if payload.get('iss') != 'ayende-pos':
                raise exceptions.AuthenticationFailed('Invalid token issuer')
            
            # Validate scope
            if payload.get('scope') != 'integration':
                raise exceptions.AuthenticationFailed('Invalid token scope')
            
            # Return None for user (system-to-system), payload for tenant context
            return (None, payload)
            
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed('Token has expired')
        except jwt.InvalidTokenError:
            raise exceptions.AuthenticationFailed('Invalid token')
        except Exception as e:
            raise exceptions.AuthenticationFailed(f'Authentication error: {str(e)}')
    
    def authenticate_header(self, request):
        """
        Return WWW-Authenticate header for 401 responses
        """
        return 'Bearer realm="api"'
