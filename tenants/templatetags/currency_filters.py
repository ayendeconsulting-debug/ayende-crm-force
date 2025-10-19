from django import template

register = template.Library()

@register.filter
def currency(value, tenant):
    """
    Format amount with tenant's currency
    Usage: {{ amount|currency:tenant }}
    """
    if not value:
        return f"{tenant.currency_symbol}0.00"
    
    # Format the number
    formatted = f"{float(value):.{tenant.decimal_places}f}"
    
    # Add currency symbol based on position
    if tenant.currency_position == 'before':
        return f"{tenant.currency_symbol}{formatted}"
    else:
        return f"{formatted}{tenant.currency_symbol}"

@register.filter
def currency_code(tenant):
    """
    Get currency code
    Usage: {{ tenant|currency_code }}
    """
    return tenant.currency