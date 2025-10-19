"""
Tenant Middleware for Ayende CX
Identifies and attaches the current tenant to each request based on subdomain
"""

from django.shortcuts import redirect
from django.urls import reverse
from django.http import HttpResponse
from tenants.models import Tenant
import logging

logger = logging.getLogger(__name__)


class TenantMiddleware:
    """
    Middleware to identify tenant from subdomain and attach to request.
    
    How it works:
    1. Extract subdomain from HTTP_HOST (e.g., 'simifood' from 'simifood.ayendecrm.com')
    2. Look up tenant by slug
    3. Attach tenant to request object
    4. All subsequent views can access request.tenant
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Domains to ignore (main platform, not tenant subdomains)
        self.excluded_domains = [
            'localhost',
            '127.0.0.1',
            'ayendecrm.com',
            'www.ayendecrm.com',
        ]
    
    def __call__(self, request):
        # Get the host from request
        host = request.get_host().split(':')[0]  # Remove port if present
        
        logger.debug(f"Processing request for host: {host}")
        
        # Initialize tenant as None
        request.tenant = None
        
        # Check if this is a main domain (not a tenant subdomain)
        if self.is_main_domain(host):
            logger.debug(f"Main domain detected: {host}")
            return self.get_response(request)
        
        # Extract subdomain
        subdomain = self.extract_subdomain(host)
        
        if subdomain:
            logger.debug(f"Subdomain detected: {subdomain}")
            
            # Look up tenant
            try:
                tenant = Tenant.objects.select_related('owner').get(
                    slug=subdomain,
                    is_active=True
                )
                request.tenant = tenant
                logger.info(f"Tenant found: {tenant.name} (ID: {tenant.id})")
                
                # Check if subscription is active
                if not self.is_subscription_active(tenant):
                    logger.warning(f"Tenant {tenant.name} has inactive subscription")
                    return HttpResponse(
                        f"<h1>Subscription Required</h1>"
                        f"<p>The subscription for {tenant.name} is not active.</p>"
                        f"<p>Please contact your administrator.</p>",
                        status=402  # Payment Required
                    )
                
            except Tenant.DoesNotExist:
                logger.warning(f"Tenant not found for subdomain: {subdomain}")
                return HttpResponse(
                    f"<h1>Business Not Found</h1>"
                    f"<p>No business found at subdomain: <strong>{subdomain}</strong></p>"
                    f"<p>Please check the URL and try again.</p>",
                    status=404
                )
            except Exception as e:
                logger.error(f"Error looking up tenant: {str(e)}")
                return HttpResponse(
                    "<h1>Error</h1><p>An error occurred while processing your request.</p>",
                    status=500
                )
        
        response = self.get_response(request)
        return response
    
    def is_main_domain(self, host):
        """Check if the host is the main platform domain (not a tenant)"""
        # Check exact matches
        if host in self.excluded_domains:
            return True
        
        # Check if it's a nip.io domain (for testing)
        if '.nip.io' in host and not self.has_subdomain_before_nip(host):
            return True
        
        return False
    
    def has_subdomain_before_nip(self, host):
        """Check if there's a subdomain before nip.io (e.g., simifood.127.0.0.1.nip.io)"""
        parts = host.split('.')
        # If we have more than 5 parts with nip.io, there's a subdomain
        # e.g., simifood.127.0.0.1.nip.io = ['simifood', '127', '0', '0', '1', 'nip', 'io']
        if 'nip' in parts and 'io' in parts:
            return len(parts) > 5
        return False
    
    def extract_subdomain(self, host):
        """
        Extract subdomain from host.
        
        Examples:
        - simifood.ayendecrm.com -> simifood
        - simifood.localhost -> simifood
        - simifood.127.0.0.1.nip.io -> simifood
        """
        parts = host.split('.')
        
        # Handle localhost (simifood.localhost)
        if 'localhost' in host and len(parts) == 2:
            return parts[0]
        
        # Handle nip.io (simifood.127.0.0.1.nip.io)
        if 'nip.io' in host:
            if len(parts) > 5:  # Has subdomain
                return parts[0]
            return None
        
        # Handle regular domains (simifood.ayendecrm.com)
        if len(parts) >= 3:
            # Don't count 'www' as a tenant subdomain
            if parts[0] != 'www':
                return parts[0]
        
        return None
    
    def is_subscription_active(self, tenant):
        """Check if tenant's subscription is active"""
        return tenant.subscription_status in ['trial', 'active']


class TenantRequiredMixin:
    """
    Mixin for views that require a tenant context.
    Use this in class-based views that should only be accessed within a tenant subdomain.
    """
    
    def dispatch(self, request, *args, **kwargs):
        if not hasattr(request, 'tenant') or request.tenant is None:
            return HttpResponse(
                "<h1>Access Denied</h1>"
                "<p>This page requires a valid business subdomain.</p>",
                status=403
            )
        return super().dispatch(request, *args, **kwargs)