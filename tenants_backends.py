"""
Tenant-Aware Authentication Backend (Parent-Level Customers)
Authenticates platform-level customers and establishes tenant context
"""

from django.contrib.auth.backends import ModelBackend
from customers.models import Customer, TenantCustomer
from tenants.utils import get_tenant_from_request


class TenantAwareAuthBackend(ModelBackend):
    """
    Authenticate platform-level customers and verify tenant relationship.
    
    Flow:
    1. Customer logs in at businessname.ayendecrm.com
    2. Backend authenticates customer (platform-level)
    3. Backend verifies customer has relationship with this tenant
    4. If valid, customer is logged in with tenant context
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate a customer and verify tenant relationship.
        
        Args:
            request: HTTP request with tenant information
            username: Customer's email or username
            password: Customer's password
        
        Returns:
            Customer object if authentication successful AND tenant relationship exists
        """
        tenant = get_tenant_from_request(request) if request else None
        
        try:
            # Find customer by email (platform-level)
            customer = Customer.objects.get(
                email=username,
                is_active=True
            )
            
            # Check password
            if not customer.check_password(password):
                return None
            
            # If logging in from tenant subdomain, verify relationship
            if tenant:
                # Check if customer has active relationship with this tenant
                has_relationship = TenantCustomer.objects.filter(
                    customer=customer,
                    tenant=tenant,
                    is_active=True
                ).exists()
                
                if not has_relationship:
                    # Customer exists but doesn't belong to this business
                    return None
            
            return customer
        
        except Customer.DoesNotExist:
            # Try by username as fallback
            try:
                customer = Customer.objects.get(
                    username=username,
                    is_active=True
                )
                
                if not customer.check_password(password):
                    return None
                
                # Verify tenant relationship if needed
                if tenant:
                    has_relationship = TenantCustomer.objects.filter(
                        customer=customer,
                        tenant=tenant,
                        is_active=True
                    ).exists()
                    
                    if not has_relationship:
                        return None
                
                return customer
            
            except Customer.DoesNotExist:
                return None
        
        return None
    
    def get_user(self, user_id):
        """Get a user by ID"""
        try:
            return Customer.objects.get(pk=user_id)
        except Customer.DoesNotExist:
            return None
