"""
Enhanced Profile URLs
"""

from django.urls import path
from . import views

app_name = 'profile'

urlpatterns = [
    # Main profile view
    path('', views.enhanced_profile, name='enhanced_profile'),
    
    # Edit sections
    path('edit/info/', views.edit_profile_info, name='edit_info'),
    path('edit/preferences/', views.edit_preferences, name='edit_preferences'),
    
    # Password
    path('security/change-password/', views.change_password, name='change_password'),
    
    # Profile picture
    path('picture/upload/', views.upload_profile_picture, name='upload_picture'),
    path('picture/delete/', views.delete_profile_picture, name='delete_picture'),
]
