from django.urls import path
from . import views

app_name = 'investment'

urlpatterns = [
    # Public landing page
    path('', views.landing_page, name='landing'),
    
    # Lead management (authenticated users only)
    path('leads/', views.lead_list, name='lead_list'),
    path('leads/<uuid:lead_id>/', views.lead_detail, name='lead_detail'),
    path('leads/<uuid:lead_id>/note/', views.add_note, name='add_note'),
    path('leads/<uuid:lead_id>/activity/', views.add_activity, name='add_activity'),
]
