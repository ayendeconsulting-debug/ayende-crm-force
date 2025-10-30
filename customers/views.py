from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from customers.models import Customer


@api_view(['GET'])
def check_customer_by_phone(request):
    """Check if customer exists by phone number"""
    phone = request.GET.get('phone')
    
    if not phone:
        return Response({'error': 'Phone number required'}, status=400)
    
    # Normalize phone number (remove non-digits)
    normalized_phone = ''.join(filter(str.isdigit, phone))
    
    # Try to find customer
    customer = Customer.objects.filter(
        phone__contains=normalized_phone,
        tenant=request.user.tenant
    ).first()
    
    if customer:
        return Response({
            'exists': True,
            'customer': {
                'id': str(customer.id),
                'crmCustomerId': str(customer.id),
                'firstName': customer.first_name,
                'lastName': customer.last_name,
                'email': customer.email,
                'phone': customer.phone,
                'address': customer.address,
                'city': customer.city,
                'state': customer.state,
                'zipCode': customer.zip_code,
                'loyaltyPoints': customer.loyalty_points,
                'loyaltyTier': customer.loyalty_tier,
                'totalSpent': float(customer.total_spent),
                'visitCount': customer.visit_count,
                'marketingOptIn': customer.marketing_opt_in,
            }
        })
    
    return Response({
        'exists': False,
        'customer': None
    })

# Create your views here.
