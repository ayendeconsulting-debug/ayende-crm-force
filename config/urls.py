from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from dashboard.views.main import landing_page, get_tenant_info  # ← Add get_tenant_info here
from dashboard.views.main import landing_page, get_tenant_info, contact_form_view
from dashboard.views import sync_views


urlpatterns = [
    # Public landing page (homepage)
    path('', landing_page, name='landing'),
    path('api/contact/', contact_form_view, name='contact_form'),
    
    # Debug endpoint (bypass tenant middleware)
    path('api/debug/tenants', get_tenant_info, name='debug_tenants'),  # ← Add this line
    
    # Admin panel
    path('admin/', admin.site.urls),
    path('', include('dashboard.urls')),
    path('notifications/', include('notifications.urls')),
    path('rewards/', include('rewards.urls')),
    path('profile/', include('profile.urls')),
    path('reports/', include('reports.urls')),
    path('investment/', include('investment.urls')),
    
    # ===== PHASE 2D: POS-to-CRM Sync Endpoints =====
    path('api/v1/sync/transaction', sync_views.receive_transaction, name='sync_transaction'),
    path('api/v1/sync/customer', sync_views.receive_customer, name='sync_customer'),
    path('api/v1/sync/health', sync_views.sync_health, name='sync_health'),
]

# Serve media files in development
if settings.DEBUG:
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)