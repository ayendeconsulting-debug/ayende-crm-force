"""
Authentication Module for Ayende CX
Contains both POS Integration JWT authentication and Multi-Tenant Customer authentication
"""

import jwt
from django.conf import settings
from django.contrib.auth.backends import BaseBackend
from django.db.models import Q
from rest_framework import authentication
from rest_framework import exceptions
from customers.models import TenantCustomer
from tenants.models import Tenant


# ============================================
# POS INTEGRATION AUTHENTICATION (Existing)
# System-to-System JWT for sync operations
# ============================================

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


# ============================================
# MULTI-TENANT CUSTOMER AUTHENTICATION (New)
# For customer login with username + tenant
# ============================================

class TenantCustomerAuthBackend(BaseBackend):
    """
    Authenticates TenantCustomer using username + tenant context.
    
    The tenant is determined from:
    1. Request subdomain (e.g., mybusiness.ayendecx.com -> "mybusiness")
    2. Explicit tenant_id or tenant_subdomain in credentials
    
    Usage in login view:
        tenant = get_tenant_from_request(request)
        user = authenticate(
            request=request,
            username=username,
            password=password,
            tenant=tenant
        )
    """
    
    def authenticate(self, request, username=None, password=None, tenant=None, tenant_id=None, tenant_subdomain=None, **kwargs):
        """
        Authenticate a TenantCustomer.
        
        Args:
            request: HTTP request (can extract tenant from subdomain)
            username: Username at the specific tenant (format: email.subdomain)
            password: Password
            tenant: Tenant object (preferred)
            tenant_id: Tenant UUID (alternative)
            tenant_subdomain: Tenant subdomain (alternative)
        
        Returns:
            TenantCustomer object if authentication succeeds, None otherwise
        """
        
        # Determine tenant
        if not tenant:
            if tenant_id:
                try:
                    tenant = Tenant.objects.get(id=tenant_id)
                except Tenant.DoesNotExist:
                    return None
            elif tenant_subdomain:
                try:
                    tenant = Tenant.objects.get(subdomain=tenant_subdomain)
                except Tenant.DoesNotExist:
                    return None
            elif request:
                # Extract tenant from request subdomain
                tenant = self._get_tenant_from_request(request)
        
        if not tenant or not username or not password:
            return None
        
        try:
            # Look up TenantCustomer by tenant + username
            tenant_customer = TenantCustomer.objects.select_related('customer', 'tenant').get(
                tenant=tenant,
                username=username,
                is_active=True
            )
            
            # Check password
            if tenant_customer.check_password(password):
                return tenant_customer
            
        except TenantCustomer.DoesNotExist:
            # Run the default password hasher once to reduce timing
            # difference between existing and non-existing users
            TenantCustomer().set_password(password)
        
        return None
    
    def get_user(self, user_id):
        """
        Get a TenantCustomer by ID.
        Used by Django to retrieve the user from the session.
        """
        try:
            return TenantCustomer.objects.select_related('customer', 'tenant').get(pk=user_id)
        except TenantCustomer.DoesNotExist:
            return None
    
    def _get_tenant_from_request(self, request):
        """
        Extract tenant from request subdomain.
        
        Examples:
            mybusiness.ayendecx.com -> subdomain = "mybusiness"
            staging.ayendecx.com -> subdomain = "staging"
            localhost:8000 -> subdomain = None (use default or require explicit)
        """
        if not request:
            return None
        
        host = request.get_host().split(':')[0]  # Remove port
        parts = host.split('.')
        
        # If we have multiple parts (subdomain.domain.tld)
        if len(parts) >= 3:
            subdomain = parts[0]
            
            # Skip common non-tenant subdomains
            if subdomain not in ['www', 'api', 'admin']:
                try:
                    return Tenant.objects.get(subdomain=subdomain)
                except Tenant.DoesNotExist:
                    pass
        
        # For localhost or no subdomain, could return a default tenant
        # or return None to require explicit tenant specification
        return None


class TenantCustomerEmailAuthBackend(BaseBackend):
    """
    Alternative authentication backend using email + tenant.
    Useful for scenarios where username is not available (e.g., password reset).
    
    Note: Since email is NOT unique across tenants, tenant context is required.
    """
    
    def authenticate(self, request, email=None, password=None, tenant=None, tenant_id=None, tenant_subdomain=None, **kwargs):
        """
        Authenticate using email + tenant + password.
        """
        
        # Determine tenant
        if not tenant:
            if tenant_id:
                try:
                    tenant = Tenant.objects.get(id=tenant_id)
                except Tenant.DoesNotExist:
                    return None
            elif tenant_subdomain:
                try:
                    tenant = Tenant.objects.get(subdomain=tenant_subdomain)
                except Tenant.DoesNotExist:
                    return None
            elif request:
                tenant = self._get_tenant_from_request(request)
        
        if not tenant or not email or not password:
            return None
        
        try:
            # Look up TenantCustomer by tenant + email
            tenant_customer = TenantCustomer.objects.select_related('customer', 'tenant').get(
                tenant=tenant,
                email=email,
                is_active=True
            )
            
            # Check password
            if tenant_customer.check_password(password):
                return tenant_customer
            
        except TenantCustomer.DoesNotExist:
            TenantCustomer().set_password(password)
        except TenantCustomer.MultipleObjectsReturned:
            # If somehow multiple accounts with same email in same tenant
            # (shouldn't happen, but handle gracefully)
            return None
        
        return None
    
    def get_user(self, user_id):
        """Get a TenantCustomer by ID"""
        try:
            return TenantCustomer.objects.select_related('customer', 'tenant').get(pk=user_id)
        except TenantCustomer.DoesNotExist:
            return None
    
    def _get_tenant_from_request(self, request):
        """Extract tenant from request subdomain"""
        if not request:
            return None
        
        host = request.get_host().split(':')[0]
        parts = host.split('.')
        
        if len(parts) >= 3:
            subdomain = parts[0]
            
            if subdomain not in ['www', 'api', 'admin']:
                try:
                    return Tenant.objects.get(subdomain=subdomain)
                except Tenant.DoesNotExist:
                    pass
        
        return None


# ============================================
# UTILITY FUNCTIONS
# ============================================

def get_tenant_from_request(request):
    """
    Helper function to extract tenant from request.
    Use this in views before calling authenticate().
    
    Usage:
        tenant = get_tenant_from_request(request)
        if not tenant:
            return Response({'error': 'Invalid tenant'}, status=400)
        
        user = authenticate(
            request=request,
            username=username,
            password=password,
            tenant=tenant
        )
    """
    if not request:
        return None
    
    host = request.get_host().split(':')[0]  # Remove port
    parts = host.split('.')
    
    # Extract subdomain
    if len(parts) >= 3:
        subdomain = parts[0]
        
        # Skip common non-tenant subdomains
        if subdomain not in ['www', 'api', 'admin']:
            try:
                return Tenant.objects.get(subdomain=subdomain)
            except Tenant.DoesNotExist:
                return None
    
    # For localhost development, you might want to:
    # 1. Return a default tenant
    # 2. Check for a tenant in session/cookies
    # 3. Return None and require explicit tenant selection
    
    return None