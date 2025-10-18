"""
Context Processors for Ayende CRMForce
Makes tenant data available in all templates
"""


def tenant_context(request):
    """
    Adds tenant information to template context.
    Makes tenant data available in all templates without explicitly passing it.
    
    Usage in templates:
    {{ tenant.name }}
    {{ tenant.logo.url }}
    {{ tenant.primary_color }}
    """
    context = {
        'tenant': None,
        'has_tenant': False,
    }
    
    if hasattr(request, 'tenant') and request.tenant:
        context['tenant'] = request.tenant
        context['has_tenant'] = True
        
        # Add commonly used tenant properties
        context['tenant_name'] = request.tenant.name
        context['tenant_logo'] = request.tenant.logo.url if request.tenant.logo else None
        context['tenant_colors'] = {
            'primary': request.tenant.primary_color,
            'secondary': request.tenant.secondary_color,
        }
        context['is_trial'] = request.tenant.is_trial
        context['is_subscribed'] = request.tenant.is_subscribed
    
    return context