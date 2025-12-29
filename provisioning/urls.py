"""
Provisioning URLs
Routes for CRM provisioning and setup wizard

Location: provisioning/urls.py
"""

from django.urls import path
from . import views

app_name = 'provisioning'

urlpatterns = [
    # Admin provisioning (requires Django admin login)
    path('provision/', views.provision_crm, name='provision_crm'),
    path('execute/', views.execute_provision, name='execute_provision'),
    path('pending/', views.pending_provisions, name='pending_provisions'),
    
    # Setup wizard (public, token-authenticated)
    path('wizard/', views.setup_wizard, name='setup_wizard'),
    path('wizard/step/<int:step>/', views.wizard_step, name='wizard_step'),
    path('wizard/complete/', views.wizard_complete, name='wizard_complete'),
]