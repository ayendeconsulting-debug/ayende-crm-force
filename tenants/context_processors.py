"""
Context processors for tenants app
Makes tenant information available in all templates
"""


def tenant_context(request):
    """
    Add tenant information to template context.
    This makes the current tenant available in all templates as {{ tenant }}
    """
    tenant = getattr(request, 'tenant', None)
    
    context = {
        'tenant': tenant,
    }
    
    # Add tenant-specific context if tenant exists
    if tenant:
        context.update({
            'tenant_name': tenant.name,
            'tenant_slug': tenant.slug,
            'tenant_currency': tenant.currency,
            'tenant_currency_symbol': tenant.currency_symbol,
            'tenant_primary_color': tenant.primary_color,
            'tenant_secondary_color': tenant.secondary_color,
            
            # FIXED: Use subscription_status instead of is_trial
            'is_trial': tenant.subscription_status == 'trial',
            'is_active_subscription': tenant.subscription_status in ['trial', 'active'],
            'subscription_status': tenant.subscription_status,
        })
        
        # Add tenant settings if available
        if hasattr(tenant, 'settings'):
            context.update({
                'allow_customer_registration': tenant.settings.allow_customer_registration,
                'enable_loyalty_points': tenant.settings.enable_loyalty_points,
                'points_per_dollar': tenant.settings.points_per_dollar,
            })
    
    return context