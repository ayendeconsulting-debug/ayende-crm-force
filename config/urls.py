from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('dashboard.urls')),
    path('notifications/', include('notifications.urls')),
    path('rewards/', include('rewards.urls')),  # ADD THIS
    path('profile/', include('profile.urls')),  # Not 'dashboard.profile.urls' # ADD THIS
    path('reports/', include('reports.urls')),  # ADD THIS LINE
]
# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)