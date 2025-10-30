"""
CRM Integration Views
Handle incoming sync requests from POS system
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.db import transaction as db_transaction
from decimal import Decimal

from customers.models import Customer, TenantCustomer, Transaction
from tenants.models import Tenant
from .serializers.sync import (
    TransactionSyncSerializer,
    CustomerSyncSerializer,
    SyncHealthSerializer
)
from .authentication import IntegrationJWTAuthentication, IntegrationPermission


class SyncHealthView(APIView):
    """
    Health check endpoint for integration
    GET /api/v1/sync/health
    """
    
    authentication_classes = [IntegrationJWTAuthentication]
    permission_classes = [IntegrationPermission]
    
    def get(self, request):
        """Return health status"""
        data = {
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'version': '1.0.0',
            'service': 'ayende-crm',
        }
        
        serializer = SyncHealthSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class TransactionSyncView(APIView):
    """
    Receive transactions from POS
    POST /api/v1/sync/transaction
    """
    
    authentication_classes = [IntegrationJWTAuthentication]
    permission_classes = [IntegrationPermission]
    
    def post(self, request):
        """
        Create or update transaction in CRM from POS data
        """
        
        serializer = TransactionSyncSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'errors': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        validated_data = serializer.validated_data
        
        try:
            with db_transaction.atomic():
                # Get or verify tenant
                try:
                    tenant = Tenant.objects.get(
                        id=validated_data['tenantId']
                    )
                except Tenant.DoesNotExist:
                    # Create tenant if it doesn't exist
                    tenant = Tenant.objects.create(
                        id=validated_data['tenantId'],
                        external_id=validated_data['tenantId'],
                        name=f"Business {validated_data['tenantId'][:8]}"
                    )
                
                # Get or create customer if provided
                customer = None
                tenant_customer = None
                
                if validated_data.get('customerId') or validated_data.get('customerEmail'):
                    customer = self._get_or_create_customer(
                        validated_data.get('customerId'),
                        validated_data.get('customerEmail'),
                        tenant
                    )
                    
                    if customer:
                        tenant_customer = TenantCustomer.objects.get_or_create(
                            customer=customer,
                            tenant=tenant,
                            defaults={'role': 'customer'}
                        )[0]
                
                # Check if transaction already exists
                existing = Transaction.objects.filter(
                    external_id=validated_data['transactionId']
                ).first()
                
                if existing:
                    # Update existing transaction
                    transaction_obj = self._update_transaction(existing, validated_data)
                    action = 'updated'
                else:
                    # Create new transaction
                    transaction_obj = self._create_transaction(
                        validated_data,
                        tenant,
                        customer,
                        tenant_customer
                    )
                    action = 'created'
                
                # Update customer stats if customer exists
                if tenant_customer:
                    self._update_customer_stats(tenant_customer, validated_data)
                
                return Response(
                    {
                        'success': True,
                        'action': action,
                        'transactionId': str(transaction_obj.id),
                        'transactionNumber': transaction_obj.transaction_id,
                        'message': f'Transaction {action} successfully'
                    },
                    status=status.HTTP_200_OK if action == 'updated' else status.HTTP_201_CREATED
                )
        
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'error': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_or_create_customer(self, customer_id, email, tenant):
        """Get or create customer"""
        if customer_id:
            customer = Customer.objects.filter(external_id=customer_id).first()
            if customer:
                return customer
        
        if email:
            customer = Customer.objects.filter(email=email).first()
            if customer:
                # Update external_id if not set
                if not customer.external_id and customer_id:
                    customer.external_id = customer_id
                    customer.save()
                return customer
        
        return None
    
    def _create_transaction(self, data, tenant, customer, tenant_customer):
        """Create new transaction"""
        transaction_obj = Transaction.objects.create(
            tenant=tenant,
            customer=customer,
            tenant_customer=tenant_customer,
            external_id=data['transactionId'],
            transaction_id=data['transactionNumber'],
            transaction_type='purchase',
            status=data['status'],
            amount=data['amount'],
            tax=data['tax'],
            total=data['total'],
            payment_method=data['paymentMethod'],
            points_earned=data['pointsEarned'],
            points_redeemed=data['pointsRedeemed'],
            items_description=self._format_items_description(data['items']),
            notes=data.get('notes', ''),
            transaction_date=data['timestamp'],
            external_source='POS'
        )
        
        return transaction_obj
    
    def _update_transaction(self, transaction_obj, data):
        """Update existing transaction"""
        transaction_obj.status = data['status']
        transaction_obj.amount = data['amount']
        transaction_obj.tax = data['tax']
        transaction_obj.total = data['total']
        transaction_obj.payment_method = data['paymentMethod']
        transaction_obj.points_earned = data['pointsEarned']
        transaction_obj.points_redeemed = data['pointsRedeemed']
        transaction_obj.items_description = self._format_items_description(data['items'])
        transaction_obj.notes = data.get('notes', '')
        transaction_obj.save()
        
        return transaction_obj
    
    def _format_items_description(self, items):
        """Format items for description"""
        descriptions = []
        for item in items:
            descriptions.append(
                f"{item['quantity']}x {item['productName']} @ ${item['unitPrice']}"
            )
        return '; '.join(descriptions)
    
    def _update_customer_stats(self, tenant_customer, data):
        """Update customer statistics"""
        if data['status'] == 'completed':
            # Update loyalty points (POS is source of truth)
            tenant_customer.loyalty_points = data['pointsEarned'] - data['pointsRedeemed']
            
            # Update totals
            tenant_customer.total_purchases = Decimal(tenant_customer.total_purchases or 0) + data['total']
            tenant_customer.total_spent = Decimal(tenant_customer.total_spent or 0) + data['total']
            tenant_customer.purchase_count += 1
            tenant_customer.last_purchase_date = data['timestamp'].date()
            tenant_customer.last_purchase_at = data['timestamp']
            
            tenant_customer.save()


class CustomerSyncView(APIView):
    """
    Receive customer updates from POS
    POST /api/v1/sync/customer
    """
    
    authentication_classes = [IntegrationJWTAuthentication]
    permission_classes = [IntegrationPermission]
    
    def post(self, request):
        """
        Create or update customer in CRM from POS data
        """
        
        serializer = CustomerSyncSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'errors': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        validated_data = serializer.validated_data
        
        try:
            with db_transaction.atomic():
                # Get or create tenant
                tenant, _ = Tenant.objects.get_or_create(
                    id=validated_data['tenantId'],
                    defaults={
                        'external_id': validated_data['tenantId'],
                        'name': f"Business {validated_data['tenantId'][:8]}"
                    }
                )
                
                # Check if customer exists by external_id or email
                customer = Customer.objects.filter(
                    external_id=validated_data['customerId']
                ).first()
                
                if not customer:
                    customer = Customer.objects.filter(
                        email=validated_data['email']
                    ).first()
                
                if customer:
                    # Update existing customer
                    customer = self._update_customer(customer, validated_data)
                    action = 'updated'
                else:
                    # Create new customer
                    customer = self._create_customer(validated_data)
                    action = 'created'
                
                # Get or create tenant-customer relationship
                tenant_customer, _ = TenantCustomer.objects.get_or_create(
                    customer=customer,
                    tenant=tenant,
                    defaults={'role': 'customer'}
                )
                
                # Update tenant-specific data (POS is source of truth for loyalty)
                tenant_customer.loyalty_points = validated_data['loyaltyPoints']
                tenant_customer.total_spent = validated_data['totalSpent']
                tenant_customer.purchase_count = validated_data['visitCount']
                
                if validated_data.get('lastVisit'):
                    tenant_customer.last_purchase_at = validated_data['lastVisit']
                    tenant_customer.last_purchase_date = validated_data['lastVisit'].date()
                
                tenant_customer.save()
                
                return Response(
                    {
                        'success': True,
                        'action': action,
                        'customerId': str(customer.id),
                        'email': customer.email,
                        'message': f'Customer {action} successfully'
                    },
                    status=status.HTTP_200_OK if action == 'updated' else status.HTTP_201_CREATED
                )
        
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'error': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _create_customer(self, data):
        """Create new customer"""
        customer = Customer.objects.create(
            external_id=data['customerId'],
            email=data['email'],
            first_name=data['firstName'],
            last_name=data['lastName'],
            phone=data.get('phone', ''),
            address=data.get('address', ''),
            city=data.get('city', ''),
            postal_code=data.get('postalCode', ''),
            country=data.get('country', 'Canada'),
            date_of_birth=data.get('dateOfBirth'),
            date_joined=data['memberSince'],
            last_synced_at=timezone.now()
        )
        
        return customer
    
    def _update_customer(self, customer, data):
        """Update existing customer"""
        customer.external_id = data['customerId']
        customer.email = data['email']
        customer.first_name = data['firstName']
        customer.last_name = data['lastName']
        customer.phone = data.get('phone', '')
        customer.address = data.get('address', '')
        customer.city = data.get('city', '')
        customer.postal_code = data.get('postalCode', '')
        customer.country = data.get('country', 'Canada')
        customer.date_of_birth = data.get('dateOfBirth')
        customer.last_synced_at = timezone.now()
        customer.save()
        
        return customer


class CustomerRetrieveView(APIView):
    """
    Get customer by email
    GET /api/v1/customers/:email
    """
    
    authentication_classes = [IntegrationJWTAuthentication]
    permission_classes = [IntegrationPermission]
    
    def get(self, request, email):
        """Return customer data by email"""
        try:
            customer = Customer.objects.get(email=email)
            
            # Get tenant-specific data
            tenant_id = request.integration_tenant_id
            tenant_customer = TenantCustomer.objects.filter(
                customer=customer,
                tenant_id=tenant_id
            ).first()
            
            data = {
                'customerId': str(customer.id),
                'email': customer.email,
                'firstName': customer.first_name,
                'lastName': customer.last_name,
                'phone': customer.phone,
                'address': customer.address,
                'city': customer.city,
                'postalCode': customer.postal_code,
                'country': customer.country,
                'dateOfBirth': customer.date_of_birth.isoformat() if customer.date_of_birth else None,
                'profilePicture': customer.profile_picture.url if customer.profile_picture else None,
                'preferredLanguage': customer.preferred_language,
                'dateJoined': customer.date_joined.isoformat(),
                'updatedAt': customer.updated_at.isoformat(),
            }
            
            if tenant_customer:
                data.update({
                    'loyaltyPoints': tenant_customer.loyalty_points,
                    'totalSpent': float(tenant_customer.total_spent),
                    'purchaseCount': tenant_customer.purchase_count,
                    'lastPurchaseDate': tenant_customer.last_purchase_date.isoformat() if tenant_customer.last_purchase_date else None,
                    'isVIP': tenant_customer.is_vip,
                    'tags': tenant_customer.tags,
                })
            
            return Response(data, status=status.HTTP_200_OK)
        
        except Customer.DoesNotExist:
            return Response(
                {
                    'success': False,
                    'error': 'Customer not found'
                },
                status=status.HTTP_404_NOT_FOUND
            )
