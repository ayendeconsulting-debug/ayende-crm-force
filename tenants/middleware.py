"""
Tenant Middleware - Fixed to bypass admin URLs
"""
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import resolve
from .models import Tenant


class TenantMiddleware:
    """
    Middleware to detect and set the current tenant based on subdomain or query parameter.
    Bypasses admin, static, and media URLs.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Get the full host
        host = request.get_host().split(':')[0]
        
        # List of URL paths to bypass tenant detection
        bypass_paths = [
            '/admin/',
            '/static/',
            '/media/',
            '/__debug__/',
        ]
        
        # Check if current path should bypass tenant detection
        should_bypass = any(request.path.startswith(path) for path in bypass_paths)
        
        if should_bypass:
            # For admin and other bypass paths, set a default tenant or None
            request.tenant = None
            return self.get_response(request)
        
        # Try to get tenant from subdomain first
        parts = host.split('.')
        tenant_slug = None
        
        # Check if we have a subdomain (more than 2 parts, excluding www)
        if len(parts) > 2:
            potential_slug = parts[0]
            if potential_slug != 'www':
                tenant_slug = potential_slug
        
        # If no subdomain, try query parameter
        if not tenant_slug:
            tenant_slug = request.GET.get('tenant')
        
        # If still no tenant slug, set None and continue
        if not tenant_slug:
            request.tenant = None
            return self.get_response(request)
        
        # Try to get the tenant
        try:
            tenant = Tenant.objects.get(slug=tenant_slug, is_active=True)
            request.tenant = tenant
        except Tenant.DoesNotExist:
            # Tenant not found - return error page
            return HttpResponse(
                f"""
                <html>
                <head><title>Business Not Found</title></head>
                <body>
                    <h1>Business Not Found</h1>
                    <p>No business found at subdomain: <strong>{tenant_slug}</strong></p>
                    <p>Please check the URL and try again.</p>
                    <hr>
                    <p><a href="/admin/">Access Admin Panel</a></p>
                </body>
                </html>
                """,
                status=404
            )
        
        response = self.get_response(request)
        return response