"""
Tenant-Aware Authentication Backend for Ayende CRMForce
Ensures users can only authenticate within their assigned tenant context
"""

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from customers.models import TenantCustomer
import logging

logger = logging.getLogger(__name__)

Customer = get_user_model()


class TenantAwareAuthBackend(ModelBackend):
    """
    Custom authentication backend that enforces tenant isolation.
    
    Users can only log in if they:
    1. Have valid credentials
    2. Have a relationship with the current tenant (via TenantCustomer)
    3. Are active in that tenant
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate user with tenant isolation
        """
        if username is None or password is None:
            return None
        
        try:
            # Get user by email (username field)
            user = Customer.objects.get(email=username)
        except Customer.DoesNotExist:
            # Run the default password hasher to reduce timing attack
            Customer().set_password(password)
            logger.debug(f"Authentication failed: User {username} does not exist")
            return None
        
        # Check password
        if not user.check_password(password):
            logger.debug(f"Authentication failed: Invalid password for {username}")
            return None
        
        # Check if user is active
        if not user.is_active:
            logger.debug(f"Authentication failed: User {username} is inactive")
            return None
        
        # If there's a tenant context, verify user belongs to this tenant
        if hasattr(request, 'tenant') and request.tenant:
            try:
                tenant_relationship = TenantCustomer.objects.get(
                    customer=user,
                    tenant=request.tenant
                )
                
                # Check if relationship is active
                if not tenant_relationship.is_active:
                    logger.warning(
                        f"Authentication failed: User {username} relationship "
                        f"with tenant {request.tenant.name} is inactive"
                    )
                    return None
                
                logger.info(
                    f"Successful authentication: {username} for tenant {request.tenant.name}"
                )
                
                # Store tenant relationship in user object for easy access
                user._tenant_relationship = tenant_relationship
                
                return user
                
            except TenantCustomer.DoesNotExist:
                logger.warning(
                    f"Authentication failed: User {username} does not belong "
                    f"to tenant {request.tenant.name}"
                )
                return None
        
        # If no tenant context (e.g., main admin site), allow superusers only
        if user.is_superuser:
            logger.info(f"Superuser authentication: {username}")
            return user
        
        logger.debug(f"Authentication failed: No tenant context for {username}")
        return None
    
    def get_user(self, user_id):
        """
        Get user by ID - standard Django backend method
        """
        try:
            return Customer.objects.get(pk=user_id)
        except Customer.DoesNotExist:
            return None
    
    def has_perm(self, user_obj, perm, obj=None):
        """
        Check if user has a specific permission
        Can be extended to include tenant-specific permissions
        """
        if not user_obj.is_active:
            return False
        
        # Superusers have all permissions
        if user_obj.is_superuser:
            return True
        
        # Check tenant-specific permissions if available
        if hasattr(user_obj, '_tenant_relationship'):
            tenant_relationship = user_obj._tenant_relationship
            
            # Example: Check custom permissions based on role
            if perm == 'customers.can_manage':
                return tenant_relationship.role in ['owner', 'admin', 'manager']
            
            if perm == 'messaging.can_send':
                return tenant_relationship.role in ['owner', 'admin', 'manager', 'staff']
        
        return False