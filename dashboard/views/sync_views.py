"""
POS-to-CRM Sync Views (Phase 2D)
Receives transaction and customer data from POS system via scheduled sync.

Endpoints:
- POST /api/v1/sync/transaction - Receive transaction from POS
- POST /api/v1/sync/customer - Receive customer updates from POS  
- GET /api/v1/sync/health - Health check for sync system

FIXED:
- Line 141: Changed customer lookup from id to external_id
- Line 328: Changed customer lookup from id to external_id
- Line 327-366: Changed to create customer if doesn't exist (not just update)
- Added context manager to prevent circular webhooks during POS sync
"""

import logging
from decimal import Decimal
from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import transaction as db_transaction
from django.conf import settings
from customers.models import Customer, Transaction
from tenants.models import Tenant
from dashboard.authentication import IntegrationJWTAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
import json
from contextvars import ContextVar

logger = logging.getLogger(__name__)

# Context variable to prevent circular webhooks during sync operations
_skip_webhooks = ContextVar('skip_webhooks', default=False)


class skip_webhooks:
    """
    Context manager to skip webhooks during POS sync operations.
    Prevents circular webhook loops when POS-originated data is synced to CRM.
    """
    def __enter__(self):
        _skip_webhooks.set(True)
        return self
    
    def __exit__(self, *args):
        _skip_webhooks.set(False)


def should_skip_webhooks():
    """
    Check if webhooks should be skipped in the current context.
    
    Returns:
        bool: True if webhooks should be skipped
    """
    return _skip_webhooks.get()


def verify_jwt_token(request):
    """
    Verify JWT token from POS system.
    
    Returns:
        tuple: (is_valid, payload_or_error_message, tenant_id)
    """
    try:
        # Get Authorization header
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header:
            return False, 'Missing Authorization header', None
        
        # Use the IntegrationJWTAuthentication class
        auth = IntegrationJWTAuthentication()
        result = auth.authenticate(request)
        
        if result is None:
            return False, 'Invalid authentication', None
        
        user, payload = result
        tenant_id = payload.get('tenantId')
        
        if not tenant_id:
            return False, 'Missing tenantId in token', None
        
        return True, payload, tenant_id
        
    except Exception as e:
        logger.error(f"JWT verification error: {str(e)}")
        return False, str(e), None


@csrf_exempt
@require_http_methods(["POST"])
def receive_transaction(request):
    """
    Receive transaction data from POS system.
    Supports both customer-linked and anonymous transactions.
    
    POST /api/v1/sync/transaction

    Expected payload:
    {
        "transactionId": "uuid",
        "transactionNumber": "TXN-001",
        "tenantId": "uuid",
        "customerId": "uuid",  // OPTIONAL - omit for anonymous transactions
        "isAnonymous": true,   // OPTIONAL - set to true for anonymous transactions
        "customerEmail": "email@example.com",
        "amount": 100.00,
        "tax": 10.00,
        "discount": 0.00,
        "total": 110.00,
        "currency": "USD",
        "paymentMethod": "CASH",
        "pointsEarned": 110,
        "pointsRedeemed": 0,
        "items": [...],
        "status": "COMPLETED",
        "timestamp": "2025-10-27T18:46:35.341Z"
    }

    Returns:
        JSON response with success/error status
    """
    try:
        # Verify JWT authentication
        is_valid, payload_or_error, tenant_id = verify_jwt_token(request)

        if not is_valid:
            logger.warning(f"Authentication failed: {payload_or_error}")
            return JsonResponse({
                'success': False,
                'error': f'Authentication failed: {payload_or_error}'
            }, status=401)

        # Parse request body
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in request body: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON in request body'
            }, status=400)

        # Validate required fields (customerId is now optional)
        required_fields = ['transactionId', 'total', 'timestamp']
        missing_fields = [field for field in required_fields if field not in data]

        if missing_fields:
            logger.error(f"Missing required fields: {missing_fields}")
            return JsonResponse({
                'success': False,
                'error': f'Missing required fields: {", ".join(missing_fields)}'
            }, status=400)

        # Get tenant
        try:
            tenant = Tenant.objects.get(tenant_uuid=tenant_id)
        except Tenant.DoesNotExist:
            logger.error(f"Tenant not found: {tenant_id}")
            return JsonResponse({
                'success': False,
                'error': f'Tenant not found: {tenant_id}'
            }, status=404)

        # Check if this is an anonymous transaction
        is_anonymous = data.get('isAnonymous', False)
        
        # WORKAROUND: If no customerId provided, treat as anonymous
        # This handles cases where POS doesn't send isAnonymous flag correctly
        if not data.get('customerId') or data.get('customerId') is None:
            is_anonymous = True
            logger.info(f"Detected anonymous transaction (no customerId): {data['transactionId']}")
        
        customer = None
        tenant_customer = None

        # Only try to get customer if not anonymous and customerId is provided
        if not is_anonymous and 'customerId' in data and data['customerId']:
            customer_id = data['customerId']
            try:
                # Get customer by external_id (POS customer ID)
                customer = Customer.objects.get(
                    external_id=customer_id, 
                    tenants__tenant_uuid=tenant_id
                )

                # Get TenantCustomer relationship
                from customers.models import TenantCustomer
                tenant_customer = TenantCustomer.objects.get(
                    customer=customer, 
                    tenant=tenant
                )

                logger.info(f"Found customer for transaction: {customer_id}")

            except Customer.DoesNotExist:
                logger.error(f"Customer not found with external_id: {customer_id}")
                return JsonResponse({
                    'success': False,
                    'error': f'Customer not found: {customer_id}'
                }, status=404)
            except TenantCustomer.DoesNotExist:
                logger.error(f"TenantCustomer relationship not found for customer: {customer_id}")
                return JsonResponse({
                    'success': False,
                    'error': f'Customer not linked to tenant'
                }, status=404)
        else:
            logger.info(f"Processing anonymous transaction: {data['transactionId']}")

        # Use database transaction to ensure atomicity
        # Use skip_webhooks context to prevent circular webhooks
        with db_transaction.atomic(), skip_webhooks():
            # Create or update transaction
            transaction_id = data['transactionId']

            # Prepare items data (ensure it's a list, not a JSON string)
            items_data = data.get('items', [])
            if isinstance(items_data, str):
                import json as json_module
                items_data = json_module.loads(items_data) if items_data else []

            # Prepare transaction defaults
            transaction_defaults = {
                'tenant': tenant,
                'customer': customer,  # Will be None for anonymous
                'tenant_customer': tenant_customer,  # Will be None for anonymous
                'is_anonymous': is_anonymous,  # NEW FIELD
                'external_source': 'POS',  # Mark as POS-originated transaction
                'transaction_number': data.get('transactionNumber', ''),
                'amount': Decimal(str(data.get('amount', 0))),
                'tax': Decimal(str(data.get('tax', 0))),
                'discount': Decimal(str(data.get('discount', 0))),
                'total': Decimal(str(data['total'])),
                'currency': data.get('currency', 'USD'),
                'payment_method': data.get('paymentMethod', 'cash').lower(),
                'points_earned': data.get('pointsEarned', 0),
                'points_redeemed': data.get('pointsRedeemed', 0),
                'items': items_data,
                'status': data.get('status', 'completed').lower(),
            }

            # Parse timestamp
            timestamp_str = data.get('timestamp')
            if timestamp_str:
                try:
                    from django.utils import timezone
                    from datetime import datetime
                    
                    # Handle ISO format timestamp
                    if timestamp_str.endswith('Z'):
                        timestamp_str = timestamp_str[:-1] + '+00:00'
                    
                    transaction_defaults['transaction_date'] = datetime.fromisoformat(timestamp_str)
                except Exception as e:
                    logger.warning(f"Could not parse timestamp: {timestamp_str}, error: {e}")
                    # Use current time if parsing fails
                    from django.utils import timezone
                    transaction_defaults['transaction_date'] = timezone.now()

            # Create or update transaction
            transaction_obj, created = Transaction.objects.update_or_create(
                external_id=transaction_id,
                defaults=transaction_defaults
            )

            action = "created" if created else "updated"
            customer_info = f"customer {customer.external_id}" if customer else "anonymous customer"
            
            logger.info(
                f"Transaction {action}: {transaction_id} for {customer_info}, "
                f"total: {data['total']}, anonymous: {is_anonymous}"
            )

            # Update customer loyalty points ONLY if not anonymous
            if not is_anonymous and customer:
                try:
                    points_earned = data.get('pointsEarned', 0)
                    points_redeemed = data.get('pointsRedeemed', 0)
                    
                    if points_earned > 0:
                        customer.loyalty_points += points_earned
                    if points_redeemed > 0:
                        customer.loyalty_points -= points_redeemed
                    
                    # Update total spent
                    customer.total_spent = (customer.total_spent or 0) + Decimal(str(data['total']))
                    
                    # Increment visit count
                    customer.visit_count = (customer.visit_count or 0) + 1
                    
                    customer.save()
                    
                    logger.info(
                        f"Updated customer loyalty: {customer.external_id}, "
                        f"points: {customer.loyalty_points}, total_spent: {customer.total_spent}"
                    )
                except Exception as e:
                    logger.error(f"Failed to update customer loyalty: {str(e)}")
                    # Don't fail the transaction if loyalty update fails

            return JsonResponse({
                'success': True,
                'action': action,
                'transaction_id': str(transaction_obj.id),
                'external_id': transaction_id,
                'is_anonymous': is_anonymous,
                'message': f'Transaction {action} successfully'
            }, status=201 if created else 200)

    except Exception as e:
        logger.error(f"Error receiving transaction: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def receive_customer(request):
    """
    Receive customer data from POS system.
    
    POST /api/v1/sync/customer
    
    Expected payload:
    {
        "customerId": "uuid",
        "tenantId": "uuid",
        "email": "email@example.com",
        "firstName": "John",
        "lastName": "Doe",
        "phone": "+1234567890",
        "loyaltyPoints": 100,
        "loyaltyTier": "BRONZE",
        "totalSpent": 150.00,
        "visitCount": 5,
        "lastVisit": "2025-10-27T18:46:35.341Z",
        "marketingOptIn": false,
        "updatedAt": "2025-10-27T18:46:35.500Z"
    }
    
    Returns:
        JSON response with success/error status
    """
    try:
        # Verify JWT authentication
        is_valid, payload_or_error, tenant_id = verify_jwt_token(request)
        
        if not is_valid:
            logger.warning(f"Authentication failed: {payload_or_error}")
            return JsonResponse({
                'success': False,
                'error': f'Authentication failed: {payload_or_error}'
            }, status=401)
        
        # Parse request body
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in request body: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON in request body'
            }, status=400)
        
        # Validate required fields
        required_fields = ['customerId', 'email', 'firstName', 'lastName']
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            logger.error(f"Missing required fields: {missing_fields}")
            return JsonResponse({
                'success': False,
                'error': f'Missing required fields: {", ".join(missing_fields)}'
            }, status=400)
        
        # Get tenant
        try:
            tenant = Tenant.objects.get(tenant_uuid=tenant_id)
        except Tenant.DoesNotExist:
            logger.error(f"Tenant not found: {tenant_id}")
            return JsonResponse({
                'success': False,
                'error': f'Tenant not found: {tenant_id}'
            }, status=404)
        
        # Use database transaction to ensure atomicity
        # Use skip_webhooks context to prevent circular webhooks
        with db_transaction.atomic(), skip_webhooks():
            customer_id = data['customerId']
            
            # FIX: Changed from id to external_id and create if doesn't exist
            try:
                customer = Customer.objects.get(external_id=customer_id, tenants__tenant_uuid=tenant_id)
                created = False
                
            except Customer.DoesNotExist:
                # Create new customer if doesn't exist
                logger.info(f"Creating new customer from POS: {customer_id}")
                
                customer = Customer.objects.create(
                    email=data['email'],
                    first_name=data['firstName'],
                    last_name=data['lastName'],
                    phone=data.get('phone') or '',  # Handle None/null values
                    external_id=customer_id,  # Store POS customer ID
                )
                
                # Create TenantCustomer relationship
                from customers.models import TenantCustomer
                TenantCustomer.objects.create(
                    customer=customer,
                    tenant=tenant,
                )
                
                created = True
            
            # Update customer fields from POS (whether new or existing)
            customer.email = data['email']
            customer.first_name = data['firstName']
            customer.last_name = data['lastName']
            customer.phone = data.get('phone') or ''  # Handle None/null values
            customer.address = data.get('address') or ''  # Handle None/null values
            customer.city = data.get('city') or ''  # Handle None/null values
            customer.state = data.get('state') or ''  # Handle None/null values
            customer.postal_code = (data.get('postalCode') or data.get('zipCode') or '')  # Handle None/null
            customer.loyalty_points = data.get('loyaltyPoints', 0)
            customer.loyalty_tier = data.get('loyaltyTier', 'BRONZE')
            customer.total_spent = Decimal(str(data.get('totalSpent', 0)))
            customer.visit_count = data.get('visitCount', 0)
            customer.marketing_opt_in = data.get('marketingOptIn', False)
            
            # Update last visit if provided
            if data.get('lastVisit'):
                customer.last_visit = datetime.fromisoformat(
                    data['lastVisit'].replace('Z', '+00:00')
                )
            
            customer.save()
            
            logger.info(f"Customer {'created' if created else 'updated'}: {customer_id}")
            
            return JsonResponse({
                'success': True,
                'message': f'Customer {"created" if created else "updated"} successfully',
                'customer': {
                    'id': str(customer.id),  # CRM customer ID
                    'external_id': customer.external_id,  # POS customer ID
                },
                'created': created
            }, status=201 if created else 200)
        
    except Exception as e:
        logger.error(f"Error processing customer sync: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def sync_health(request):
    """
    Health check endpoint for sync system.
    
    GET /api/v1/sync/health
    
    Returns:
        JSON response with system status
    """
    try:
        # Check if sync is enabled
        enable_crm_sync = getattr(settings, 'ENABLE_CRM_SYNC', False)
        
        # Get configuration
        pos_webhook_url = getattr(settings, 'POS_WEBHOOK_URL', None)
        integration_secret_configured = bool(getattr(settings, 'INTEGRATION_SECRET', None))
        
        return JsonResponse({
            'status': 'healthy',
            'sync_enabled': enable_crm_sync,
            'webhook_url_configured': bool(pos_webhook_url),
            'integration_secret_configured': integration_secret_configured,
            'timestamp': datetime.now().isoformat(),
        })
        
    except Exception as e:
        logger.error(f"Health check error: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat(),
        }, status=500)

@api_view(['GET'])
@authentication_classes([IntegrationJWTAuthentication])
def get_updated_customers(request):
    """
    Get customers updated since a specific time.
    Used by POS for scheduled sync (CRM → POS).
    
    GET /api/sync/customers?updated_since=2025-11-08T12:00:00Z
    
    Query params:
    - updated_since: ISO timestamp (optional) - only return customers updated after this time
    
    Returns:
        JSON response with list of customers
    """
    try:
        # Verify JWT authentication (already done by decorator)
        # Get tenant from JWT payload
        tenant_id = request.auth_payload.get('tenantId')
        
        if not tenant_id:
            return Response({
                'success': False,
                'error': 'Missing tenantId in token'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get tenant
        try:
            tenant = Tenant.objects.get(tenant_uuid=tenant_id)
        except Tenant.DoesNotExist:
            logger.error(f"Tenant not found: {tenant_id}")
            return Response({
                'success': False,
                'error': f'Tenant not found: {tenant_id}'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get updated_since parameter
        updated_since = request.GET.get('updated_since')
        
        # Import TenantCustomer
        from customers.models import TenantCustomer
        
        # Build query
        query = TenantCustomer.objects.filter(tenant=tenant, is_active=True)
        
        if updated_since:
            try:
                # Parse ISO format timestamp
                since_time = datetime.fromisoformat(updated_since.replace('Z', '+00:00'))
                query = query.filter(updated_at__gte=since_time)
                logger.info(f"Fetching customers updated since: {since_time}")
            except ValueError as e:
                logger.error(f"Invalid updated_since format: {updated_since}")
                return Response({
                    'success': False,
                    'error': 'Invalid updated_since format. Use ISO 8601 format (e.g., 2025-11-08T12:00:00Z)'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get customers (limit to 100 per request)
        tenant_customers = query.select_related('customer').order_by('updated_at')[:100]
        
        logger.info(f"Found {tenant_customers.count()} customers for sync")
        
        # Serialize customers
        customers = []
        for tc in tenant_customers:
            customers.append({
                'id': str(tc.customer.id),  # CRM customer ID
                'external_id': str(tc.external_id) if tc.external_id else None,  # POS customer ID
                'first_name': tc.customer.first_name,
                'last_name': tc.customer.last_name,
                'email': tc.customer.email,
                'phone': tc.customer.phone,
                'address': getattr(tc.customer, 'address', ''),
                'city': getattr(tc.customer, 'city', ''),
                'state': getattr(tc.customer, 'state', ''),
                'postal_code': getattr(tc.customer, 'postal_code', ''),
                'loyalty_points': tc.loyalty_points if hasattr(tc, 'loyalty_points') else 0,
                'loyalty_tier': getattr(tc, 'loyalty_tier', 'BRONZE'),
                'total_spent': float(tc.total_spent) if hasattr(tc, 'total_spent') else 0.0,
                'visit_count': tc.purchase_count if hasattr(tc, 'purchase_count') else 0,
                'marketing_opt_in': getattr(tc.customer, 'marketing_opt_in', False),
                'is_active': tc.is_active,
                'updated_at': tc.updated_at.isoformat() if hasattr(tc, 'updated_at') else None,
            })
        
        return Response({
            'success': True,
            'count': len(customers),
            'customers': customers,
            'has_more': len(customers) >= 100,  # Indicates if there are more results
            'timestamp': datetime.now().isoformat()
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error fetching customers for sync: {str(e)}", exc_info=True)
        return Response({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)