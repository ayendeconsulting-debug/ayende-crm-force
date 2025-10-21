from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from dashboard.views import landing_page

urlpatterns = [
    # Public landing page (homepage)
    path('', landing_page, name='landing'),
    
    # Admin panel
    path('admin/', admin.site.urls),
    path('', include('dashboard.urls')),
    path('notifications/', include('notifications.urls')),
    path('rewards/', include('rewards.urls')),  # ADD THIS
    path('profile/', include('profile.urls')),  # Not 'dashboard.profile.urls' # ADD THIS
    path('reports/', include('reports.urls')),  # ADD THIS LINE
]
# Serve media files in development
if settings.DEBUG:
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)