"""
POS-to-CRM Sync Views (Phase 4 Updated)
Receives transaction and customer data from POS system via scheduled sync.

PHASE 4 UPDATES:
- Updated to use TenantCustomer with username format: email.subdomain
- Uses external_id for customer mapping between POS and CRM
- Tenant-scoped queries for all operations
- Supports anonymous transactions

Endpoints:
- POST /api/v1/sync/transaction - Receive transaction from POS
- POST /api/v1/sync/customer - Receive customer updates from POS  
- GET /api/v1/sync/health - Health check for sync system
- GET /api/sync/customers - Get updated customers (CRM to POS)
"""

import logging
from decimal import Decimal
from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import transaction as db_transaction
from django.conf import settings
from customers.models import Customer, TenantCustomer, Transaction, RentalContract, RentalContractItem
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
    PHASE 4: Uses TenantCustomer with external_id mapping
    
    POST /api/v1/sync/transaction

    Expected payload:
    {
        "transactionId": "uuid",
        "transactionNumber": "TXN-001",
        "tenantId": "uuid",
        "tenantCustomerId": "pos_customer_id",  // OPTIONAL - POS customer ID (external_id)
        "isAnonymous": true,   // OPTIONAL - set to true for anonymous transactions
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
        "timestamp": "2025-11-09T18:46:35.341Z"
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
        
        # If no tenantCustomerId provided, treat as anonymous
        if not data.get('tenantCustomerId'):
            is_anonymous = True
            logger.info(f"Detected anonymous transaction (no tenantCustomerId): {data['transactionId']}")
        
        tenant_customer = None

        # Only try to get customer if not anonymous and tenantCustomerId is provided
        if not is_anonymous and 'tenantCustomerId' in data and data['tenantCustomerId']:
            pos_customer_id = data['tenantCustomerId']
            try:
                # PHASE 4: Find TenantCustomer by external_id
                tenant_customer = TenantCustomer.objects.get(
                    tenant=tenant,
                    external_id=pos_customer_id
                )
                logger.info(f"Found TenantCustomer for transaction: {pos_customer_id}")

            except TenantCustomer.DoesNotExist:
                logger.error(f"TenantCustomer not found with external_id: {pos_customer_id}")
                return JsonResponse({
                    'success': False,
                    'error': f'Customer not found. Please sync customer first: {pos_customer_id}'
                }, status=404)
        else:
            logger.info(f"Processing anonymous transaction: {data['transactionId']}")

        # Use database transaction to ensure atomicity
        with db_transaction.atomic(), skip_webhooks():
            # Create or update transaction
            transaction_id = data['transactionId']

            # Prepare items data
            items_data = data.get('items', [])
            if isinstance(items_data, str):
                items_data = json.loads(items_data) if items_data else []

            # Prepare transaction defaults
            transaction_defaults = {
                'tenant': tenant,
                'tenant_customer': tenant_customer,  # Will be None for anonymous
                'is_anonymous': is_anonymous,
                'external_source': 'POS',
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
                    
                    # Handle ISO format timestamp
                    if timestamp_str.endswith('Z'):
                        timestamp_str = timestamp_str[:-1] + '+00:00'
                    
                    transaction_defaults['transaction_date'] = datetime.fromisoformat(timestamp_str)
                except Exception as e:
                    logger.warning(f"Could not parse timestamp: {timestamp_str}, error: {e}")
                    from django.utils import timezone
                    transaction_defaults['transaction_date'] = timezone.now()

            # Create or update transaction
            transaction_obj, created = Transaction.objects.update_or_create(
                external_id=transaction_id,
                defaults=transaction_defaults
            )

            action = "created" if created else "updated"
            customer_info = f"TenantCustomer {tenant_customer.external_id}" if tenant_customer else "anonymous"
            
            logger.info(
                f"Transaction {action}: {transaction_id} for {customer_info}, "
                f"total: {data['total']}, anonymous: {is_anonymous}"
            )

            # Update customer stats ONLY if not anonymous
            if not is_anonymous and tenant_customer:
                try:
                    points_earned = data.get('pointsEarned', 0)
                    points_redeemed = data.get('pointsRedeemed', 0)
                    
                    if points_earned > 0:
                        tenant_customer.loyalty_points += points_earned
                    if points_redeemed > 0:
                        tenant_customer.loyalty_points -= points_redeemed
                    
                    # Update total spent
                    tenant_customer.total_spent = (tenant_customer.total_spent or 0) + Decimal(str(data['total']))
                    
                    # Increment purchase count
                    tenant_customer.purchase_count = (tenant_customer.purchase_count or 0) + 1
                    
                    # Update last purchase date
                    from django.utils import timezone
                    tenant_customer.last_purchase_at = timezone.now()
                    
                    tenant_customer.save()
                    logger.info(f"Updated TenantCustomer stats: points={tenant_customer.loyalty_points}, spent={tenant_customer.total_spent}")
                    
                except Exception as e:
                    logger.error(f"Error updating customer stats: {str(e)}")
                    # Don't fail the whole transaction if stats update fails
            
            return JsonResponse({
                'success': True,
                'message': f'Transaction {action} successfully',
                'transaction': {
                    'id': str(transaction_obj.id),
                    'external_id': transaction_obj.external_id,
                },
                'created': created
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
    PHASE 4: Creates/updates TenantCustomer with username format email.subdomain
    
    POST /api/v1/sync/customer
    
    Expected payload:
    {
        "customerId": "pos_customer_id",  // POS system's customer ID
        "tenantId": "uuid",
        "email": "john@example.com",
        "firstName": "John",
        "lastName": "Doe",
        "phone": "+1234567890",
        "loyaltyPoints": 100,
        "loyaltyTier": "BRONZE",
        "totalSpent": 150.00,
        "visitCount": 5,
        "lastVisit": "2025-11-09T18:46:35.341Z",
        "marketingOptIn": false,
        "updatedAt": "2025-11-09T18:46:35.500Z"
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
        with db_transaction.atomic(), skip_webhooks():
            pos_customer_id = data['customerId']
            email = data['email']
            first_name = data['firstName']
            last_name = data['lastName']
            
            # PHASE 4: Generate username: email.subdomain
            username = f"{email}.{tenant.subdomain}"
            
            # Get or create global Customer (for cross-tenant linking)
            customer, customer_created = Customer.objects.get_or_create(
                first_name=first_name,
                last_name=last_name
            )
            
            # Create or update TenantCustomer
            tenant_customer, created = TenantCustomer.objects.update_or_create(
                tenant=tenant,
                external_id=pos_customer_id,  # POS customer ID
                defaults={
                    'customer': customer,
                    'username': username,  # PHASE 4: Format email.subdomain
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'phone': data.get('phone', ''),
                    'loyalty_points': data.get('loyaltyPoints', 0),
                    'loyalty_tier': data.get('loyaltyTier', 'BRONZE'),
                    'total_spent': Decimal(str(data.get('totalSpent', 0))),
                    'visit_count': data.get('visitCount', 0),
                    'marketing_opt_in': data.get('marketingOptIn', False),
                    'role': 'customer',
                    'is_active': True,
                    'email_verified': True,  # POS customers are pre-verified
                }
            )
            
            # Update last visit if provided
            if data.get('lastVisit'):
                try:
                    tenant_customer.last_visit = datetime.fromisoformat(
                        data['lastVisit'].replace('Z', '+00:00')
                    )
                    tenant_customer.save()
                except Exception as e:
                    logger.warning(f"Could not parse lastVisit: {e}")
            
            logger.info(
                f"TenantCustomer {'created' if created else 'updated'}: {pos_customer_id}, "
                f"username: {username}, email: {email}"
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Customer {"created" if created else "updated"} successfully',
                'customer': {
                    'id': str(tenant_customer.id),  # CRM tenant customer ID
                    'username': tenant_customer.username,  # PHASE 4: Return username
                    'external_id': tenant_customer.external_id,  # POS customer ID
                    'email': tenant_customer.email,
                },
                'created': created
            }, status=201 if created else 200)
        
    except Exception as e:
        logger.error(f"Error processing customer sync: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }, status=500)


def get_updated_customers(request):
    """
    Return list of customers updated since given timestamp (CRM to POS sync)
    PHASE 4: Returns TenantCustomer data with username
    
    GET /api/sync/customers?updated_since=2025-11-09T10:00:00Z&limit=100
    
    Query params:
        updated_since: ISO timestamp (optional)
        limit: Number of records to return (default: 100, max: 100)
    
    Returns:
    {
        "customers": [
            {
                "id": "uuid",
                "username": "email.subdomain",
                "email": "customer@example.com",
                "firstName": "John",
                "lastName": "Doe",
                "phone": "+1234567890",
                "loyaltyPoints": 100,
                "totalSpent": "500.00",
                "externalId": "pos_customer_id",
                "updatedAt": "2025-11-09T10:00:00Z"
            },
            ...
        ],
        "count": 10,
        "hasMore": false
    }
    """
    # Verify JWT authentication
    is_valid, payload_or_error, tenant_id = verify_jwt_token(request)
    
    if not is_valid:
        logger.warning(f"Authentication failed: {payload_or_error}")
        return JsonResponse({
            'error': f'Authentication failed: {payload_or_error}'
        }, status=401)
    
    # Get tenant
    try:
        tenant = Tenant.objects.get(tenant_uuid=tenant_id)
    except Tenant.DoesNotExist:
        logger.error(f"Tenant not found: {tenant_id}")
        return JsonResponse({
            'error': f'Tenant not found: {tenant_id}'
        }, status=404)
    updated_since = request.GET.get('updated_since')
    limit = min(int(request.GET.get('limit', 100)), 100)  # Max 100
    
    # Build query
    queryset = TenantCustomer.objects.filter(tenant=tenant)
    
    if updated_since:
        from django.utils import timezone
        try:
            updated_since_dt = datetime.fromisoformat(updated_since.replace('Z', '+00:00'))
            queryset = queryset.filter(updated_at__gte=updated_since_dt)
        except ValueError:
            return JsonResponse({'error': 'Invalid updated_since format. Use ISO format.'}, status=400)
    
    # Order by updated_at and limit
    queryset = queryset.order_by('-updated_at')[:limit + 1]  # Get one extra to check if more exist
    
    customers = []
    for tc in queryset[:limit]:
        customers.append({
            'id': str(tc.id),
            'username': tc.username,  # PHASE 4: Include username
            'email': tc.email,
            'firstName': tc.first_name,
            'lastName': tc.last_name,
            'phone': tc.phone,
            'loyaltyPoints': tc.loyalty_points,
            'totalSpent': str(tc.total_spent) if tc.total_spent else '0.00',
            'externalId': str(tc.external_id) if tc.external_id else None,
            'updatedAt': tc.updated_at.isoformat() if tc.updated_at else None,
        })
    
    return JsonResponse({
        'customers': customers,
        'count': len(customers),
        'hasMore': len(queryset) > limit
    })


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
            'service': 'ayende-crm',
            'version': '2.0',  # PHASE 4 version
            'sync_enabled': enable_crm_sync,
            'webhook_url_configured': bool(pos_webhook_url),
            'integration_secret_configured': integration_secret_configured,
            'features': {
                'multi_tenant': True,
                'username_format': 'email.subdomain',
                'customer_sync': True,
                'transaction_sync': True,
                'anonymous_transactions': True,
                'rental_sync': True,
            },
            'timestamp': datetime.now().isoformat(),
        })
        
    except Exception as e:
        logger.error(f"Health check error: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat(),
        }, status=500)


# ============================================================================
# RENTAL SYNC ENDPOINT (Added for POS-CRM Rental Sync)
# ============================================================================

@csrf_exempt
@require_http_methods(["POST"])
def receive_rental(request):
    """
    Receive rental contract data from POS system.
    
    POST /api/v1/sync/rental
    
    Expected payload:
    {
        "rentalId": "uuid",
        "contractNumber": "RNT-001",
        "tenantId": "uuid",
        "operation": "create",
        "tenantCustomerId": "pos_customer_id",
        "customerName": "John Doe",
        "startDate": "2025-11-28T10:00:00Z",
        "expectedReturnDate": "2025-12-05T10:00:00Z",
        "status": "ACTIVE",
        "items": [...],
        ...
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
        required_fields = ['rentalId', 'contractNumber', 'startDate', 'expectedReturnDate']
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
        
        # Get operation type
        operation = data.get('operation', 'create').lower()
        
        # Find customer if provided
        tenant_customer = None
        if data.get('tenantCustomerId'):
            try:
                tenant_customer = TenantCustomer.objects.get(
                    tenant=tenant,
                    external_id=data['tenantCustomerId']
                )
            except TenantCustomer.DoesNotExist:
                logger.warning(f"TenantCustomer not found for rental: {data['tenantCustomerId']}")
        
        # Use database transaction to ensure atomicity
        with db_transaction.atomic(), skip_webhooks():
            rental_id = data['rentalId']
            
            # Parse dates helper
            def parse_datetime(dt_str):
                if not dt_str:
                    return None
                try:
                    if dt_str.endswith('Z'):
                        dt_str = dt_str[:-1] + '+00:00'
                    return datetime.fromisoformat(dt_str)
                except Exception as e:
                    logger.warning(f"Could not parse datetime: {dt_str}, error: {e}")
                    return None
            
            # Prepare rental defaults
            rental_defaults = {
                'tenant': tenant,
                'contract_number': data.get('contractNumber', ''),
                'tenant_customer': tenant_customer,
                'customer_name': data.get('customerName', ''),
                'contact_phone': data.get('contactPhone', ''),
                'contact_email': data.get('contactEmail', ''),
                'delivery_address': data.get('deliveryAddress', ''),
                'start_date': parse_datetime(data['startDate']),
                'expected_return_date': parse_datetime(data['expectedReturnDate']),
                'actual_return_date': parse_datetime(data.get('actualReturnDate')),
                'rental_days': data.get('rentalDays', 1),
                'subtotal': Decimal(str(data.get('subtotal', 0))),
                'tax_amount': Decimal(str(data.get('taxAmount', 0))),
                'deposit_amount': Decimal(str(data.get('depositAmount', 0))),
                'deposit_returned': Decimal(str(data['depositReturned'])) if data.get('depositReturned') else None,
                'penalty_amount': Decimal(str(data.get('penaltyAmount', 0))),
                'damage_charges': Decimal(str(data.get('damageCharges', 0))),
                'total_due': Decimal(str(data.get('totalDue', 0))),
                'total_paid': Decimal(str(data.get('totalPaid', 0))),
                'balance_due': Decimal(str(data.get('balanceDue', 0))),
                'currency': data.get('currency', '$'),
                'currency_code': data.get('currencyCode', 'CAD'),
                'status': data.get('status', 'active').lower(),
                'return_notes': data.get('returnNotes', ''),
                'damage_notes': data.get('damageNotes', ''),
                'overdue_notified': data.get('overdueNotified', False),
                'overdue_notified_at': parse_datetime(data.get('overdueNotifiedAt')),
                'reminder_sent': data.get('reminderSent', False),
                'reminder_sent_at': parse_datetime(data.get('reminderSentAt')),
                'transaction_id': data.get('transactionId'),
                'closed_at': parse_datetime(data.get('closedAt')),
                'external_source': 'POS',
            }
            
            # Create or update rental contract
            rental_obj, created = RentalContract.objects.update_or_create(
                external_id=rental_id,
                tenant=tenant,
                defaults=rental_defaults
            )
            
            # Process rental items
            items_data = data.get('items', [])
            if items_data:
                # Delete existing items and recreate
                rental_obj.items.all().delete()
                
                for item_data in items_data:
                    RentalContractItem.objects.create(
                        contract=rental_obj,
                        product_id=item_data.get('productId', ''),
                        product_name=item_data.get('productName', ''),
                        sku=item_data.get('sku', ''),
                        quantity=item_data.get('quantity', 1),
                        daily_rate=Decimal(str(item_data.get('dailyRate', 0))),
                        subtotal=Decimal(str(item_data.get('subtotal', 0))),
                        returned_quantity=item_data.get('returnedQuantity', 0),
                        damaged_quantity=item_data.get('damagedQuantity', 0),
                        missing_quantity=item_data.get('missingQuantity', 0),
                        damage_description=item_data.get('damageDescription', ''),
                        damage_charge=Decimal(str(item_data.get('damageCharge', 0))),
                        returned_at=parse_datetime(item_data.get('returnedAt')),
                    )
            
            action = "created" if created else "updated"
            customer_info = f"TenantCustomer {tenant_customer.external_id}" if tenant_customer else data.get('customerName', 'Unknown')
            
            logger.info(
                f"Rental {action}: {rental_id} ({data.get('contractNumber')}) for {customer_info}, "
                f"status: {data.get('status')}, operation: {operation}"
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Rental {action} successfully',
                'rental': {
                    'id': str(rental_obj.id),
                    'external_id': rental_obj.external_id,
                    'contract_number': rental_obj.contract_number,
                    'status': rental_obj.status,
                },
                'created': created
            }, status=201 if created else 200)
    
    except Exception as e:
        logger.error(f"Error processing rental sync: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }, status=500)
