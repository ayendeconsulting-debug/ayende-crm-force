from django.shortcuts import render
from django.utils.deprecation import MiddlewareMixin
from .models import Tenant

class TenantMiddleware(MiddlewareMixin):
    """
    Middleware to set the current tenant based on subdomain.
    Bypasses tenant detection for admin, static files, media, and landing page.
    """
    
    def process_request(self, request):
        # Get the host from the request
        host = request.get_host().split(':')[0].lower()
        
        # IMPORTANT: Bypass tenant detection for these paths
        exempt_paths = [
            '/admin/',
            '/static/',
            '/media/',
            '/',  # Landing page - bypass tenant check
        ]
        
        # Check if the current path should bypass tenant detection
        for path in exempt_paths:
            if request.path.startswith(path):
                request.tenant = None
                return None
        
        # Extract subdomain (if exists)
        subdomain = None
        parts = host.split('.')
        
        # Check if we have a subdomain (more than 2 parts or specific Railway pattern)
        if len(parts) > 2:
            # For railway.app: subdomain.railway.app
            # For custom domains: subdomain.example.com
            subdomain = parts[0]
        elif 'railway.app' in host:
            # For Railway URLs like: ayende-cx-production.up.railway.app
            # Treat the full host as subdomain
            subdomain = parts[0]
        
        # If no subdomain or localhost, set tenant to None
        if not subdomain or subdomain in ['localhost', '127.0.0.1', 'www']:
            request.tenant = None
            return None
        
        # Try to get tenant by subdomain
        try:
            tenant = Tenant.objects.get(subdomain=subdomain, is_active=True)
            request.tenant = tenant
        except Tenant.DoesNotExist:
            request.tenant = None
            # Show "Business Not Found" page only for non-exempt paths
            return render(request, 'errors/business_not_found.html', {
                'subdomain': subdomain,
            }, status=404)
        
        return None