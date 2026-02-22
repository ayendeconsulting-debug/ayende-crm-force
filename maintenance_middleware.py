"""
Maintenance Mode Middleware

To enable maintenance mode:
1. Set MAINTENANCE_MODE = True in settings.py or environment variable
2. Restart the application

The maintenance page will be shown to all visitors except:
- Requests to /admin/ (so you can still access admin)
- Superusers who are logged in
"""

from django.conf import settings
from django.shortcuts import render
from django.http import HttpResponse


class MaintenanceModeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if maintenance mode is enabled
        maintenance_mode = getattr(settings, 'MAINTENANCE_MODE', False)
        
        if maintenance_mode:
            # Allow admin access
            if request.path.startswith('/admin/'):
                return self.get_response(request)
            
            # Allow superusers to bypass maintenance
            if request.user.is_authenticated and request.user.is_superuser:
                return self.get_response(request)
            
            # Show maintenance page to everyone else
            return render(request, 'maintenance.html', status=503)
        
        return self.get_response(request)
