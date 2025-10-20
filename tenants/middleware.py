from django.shortcuts import render
from django.utils.deprecation import MiddlewareMixin
from .models import Tenant

class TenantMiddleware(MiddlewareMixin):
    """
    Middleware to set the current tenant based on subdomain.
    Bypasses tenant detection for admin, static files, and media.
    Landing page (/) SHOULD detect tenant to show tenant-specific branding.
    """
    
    def process_request(self, request):
        # Get the host from the request
        host = request.get_host().split(':')[0].lower()
        
        # IMPORTANT: Bypass tenant detection for these paths ONLY
        exempt_paths = [
            '/admin/',
            '/static/',
            '/media/',
        ]
        
        # Check if the current path should bypass tenant detection
        for path in exempt_paths:
            if request.path.startswith(path):
                request.tenant = None
                return None
        
        # Extract subdomain (if exists)
        subdomain = None
        parts = host.split('.')
        
        # Determine subdomain based on host pattern
        if len(parts) >= 2:
            # Check for special localhost case
            if parts[-1] == 'localhost':
                # For localhost: subdomain.localhost
                if len(parts) == 2 and parts[0] not in ['localhost', 'www']:
                    subdomain = parts[0]
            elif 'railway.app' in host:
                # For Railway: subdomain.railway.app or service.up.railway.app
                if len(parts) >= 3:
                    subdomain = parts[0]
            elif len(parts) >= 3:
                # For custom domains: subdomain.example.com
                # Skip if it's www or the base domain
                if parts[0] not in ['www', 'ayendecx']:
                    subdomain = parts[0]
        
        # If no subdomain, set tenant to None
        if not subdomain:
            request.tenant = None
            return None
        
        # Try to get tenant by subdomain
        try:
            tenant = Tenant.objects.get(subdomain=subdomain, is_active=True)
            request.tenant = tenant
        except Tenant.DoesNotExist:
            request.tenant = None
            # Show "Business Not Found" page
            return render(request, 'errors/business_not_found.html', {
                'subdomain': subdomain,
            }, status=404)
        
        return None