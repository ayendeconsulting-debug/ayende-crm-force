"""
URL Configuration for Rewards App
"""

from django.urls import path
from . import views

app_name = 'rewards'

urlpatterns = [
    # Customer URLs - Rewards Catalog & Redemption
    path('', views.rewards_catalog, name='catalog'),
    path('reward/<uuid:reward_id>/', views.reward_detail, name='detail'),
    path('reward/<uuid:reward_id>/redeem/', views.redeem_reward, name='redeem'),
    path('my-redemptions/', views.my_redemptions, name='my_redemptions'),
    path('redemption/<uuid:redemption_id>/', views.redemption_detail_customer, name='redemption_detail'),
    
    # Business Owner URLs - Rewards Management
    path('manage/', views.manage_rewards, name='manage'),
    path('manage/create/', views.create_reward, name='create'),
    path('manage/<uuid:reward_id>/edit/', views.edit_reward, name='edit'),
    path('manage/<uuid:reward_id>/delete/', views.delete_reward, name='delete'),
    
    # Business Owner URLs - Redemption Management
    path('manage/redemptions/', views.manage_redemptions, name='manage_redemptions'),
    path('manage/redemption/<uuid:redemption_id>/', views.redemption_detail_business, name='redemption_detail_business'),
    path('manage/redemptions/quick-use/', views.use_redemption_quick, name='quick_use'),
]
