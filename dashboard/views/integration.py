"""
Integration Views for POS Sync
Handles transaction and customer sync from POS system
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status
from datetime import datetime

from dashboard.authentication import IntegrationJWTAuthentication
from dashboard.serializers.sync import (
    TransactionSyncSerializer,
    CustomerSyncSerializer,
    CustomerBatchSyncSerializer
)
from customers.models import Customer, Transaction, TenantCustomer
from tenants.models import Tenant


class SyncHealthView(APIView):
    """
    Health check endpoint for integration
    Returns status of CRM system
    """
    authentication_classes = [IntegrationJWTAuthentication]
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Check if CRM is healthy and ready to receive data"""
        return Response({
            'status': 'healthy',
            'message': 'CRM system is ready to receive sync requests',
            'version': '1.0.0',
            'timestamp': datetime.now().isoformat()
        })


class TransactionSyncView(APIView):
    """
    Receive transaction data from POS system
    """
    authentication_classes = [IntegrationJWTAuthentication]
    permission_classes = [AllowAny]
    
    def post(self, request):
        """
        Sync a transaction from POS to CRM
        
        Expected payload:
        {
            "transactionId": "uuid",
            "tenantId": "a-cx-xxxxx",
            "customerId": "uuid",
            "customerEmail": "email@example.com",
            "amount": 150.00,
            "tax": 19.50,
            "total": 169.50,
            "paymentMethod": "CARD",
            "pointsEarned": 169,
            "pointsRedeemed": 0,
            "items": [...],
            "timestamp": "2025-10-25T10:30:00Z"
        }
        """
        serializer = TransactionSyncSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Invalid transaction data',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            data = serializer.validated_data
            
            # Get tenant
            try:
                tenant = Tenant.objects.get(pk=data['tenantId'])
            except Tenant.DoesNotExist:
                return Response({
                    'success': False,
                    'message': 'Tenant not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Get tenant customer by external_id
            try:
                tenant_customer = TenantCustomer.objects.get(
                    external_id=data['customerId'],
                    tenant=tenant
                )
            except TenantCustomer.DoesNotExist:
                return Response({
                    'success': False,
                    'message': 'Customer not found for this tenant'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Create or update transaction
            transaction, created = Transaction.objects.update_or_create(
                transaction_id=data['transactionId'],
                tenant=tenant,
                defaults={
                    'tenant_customer': tenant_customer,
                    'amount': data['amount'],
                    'tax': data['tax'],
                    'total': data['total'],
                    'payment_method': data['paymentMethod'],
                    'points_earned': data['pointsEarned'],
                    'points_redeemed': data['pointsRedeemed'],
                    'transaction_date': data['timestamp'],
                    'external_source': 'POS',
                    'external_id': data['transactionId'],
                }
            )
            
            print(f"✅ Transaction {data['transactionId']} {'created' if created else 'updated'} from POS")
            
            return Response({
                'success': True,
                'message': f'Transaction {"created" if created else "updated"} successfully',
                'entityId': str(transaction.transaction_id),
                'created': created
            }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
            
        except Exception as e:
            print(f"❌ Error syncing transaction: {str(e)}")
            return Response({
                'success': False,
                'message': f'Error processing transaction: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CustomerSyncView(APIView):
    """
    Receive customer data from POS system
    """
    authentication_classes = [IntegrationJWTAuthentication]
    permission_classes = [AllowAny]
    
    def post(self, request):
        """
        Sync a customer from POS to CRM
        
        Expected payload:
        {
            "customerId": "uuid",
            "tenantId": "a-cx-xxxxx",
            "email": "customer@email.com",
            "firstName": "John",
            "lastName": "Doe",
            "phone": "+1234567890",
            "loyaltyPoints": 1500,
            "totalSpent": 1500.00,
            ...
        }
        """
        serializer = CustomerSyncSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Invalid customer data',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            data = serializer.validated_data
            
            # Get tenant
            try:
                tenant = Tenant.objects.get(pk=data['tenantId'])
            except Tenant.DoesNotExist:
                return Response({
                    'success': False,
                    'message': 'Tenant not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Generate username in the format: email.subdomain
            username = f"{data['email']}.{tenant.subdomain}"
            
            # Create or update TenantCustomer directly
            tenant_customer, created = TenantCustomer.objects.update_or_create(
                external_id=data['customerId'],
                tenant=tenant,
                defaults={
                    'username': username,
                    'email': data['email'],
                    'first_name': data['firstName'],
                    'last_name': data['lastName'],
                    'phone': data.get('phone', ''),
                    'loyalty_points': data.get('loyaltyPoints', 0),
                    'total_spent': data.get('totalSpent', 0),
                    'visit_count': data.get('visitCount', 0),
                    'is_active': True,
                    'role': 'customer',
                }
            )
            
            print(f"✅ Customer {data['email']} {'created' if created else 'updated'} from POS")
            
            return Response({
                'success': True,
                'message': f'Customer {"created" if created else "updated"} successfully',
                'entityId': str(tenant_customer.id),
                'created': created
            }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
            
        except Exception as e:
            print(f"❌ Error syncing customer: {str(e)}")
            return Response({
                'success': False,
                'message': f'Error processing customer: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CustomerBatchSyncView(APIView):
    """
    Receive batch customer data from POS system
    """
    authentication_classes = [IntegrationJWTAuthentication]
    permission_classes = [AllowAny]
    
    def post(self, request):
        """
        Sync multiple customers in batch
        
        Expected payload:
        {
            "tenantId": "a-cx-xxxxx",
            "customers": [...]
        }
        """
        serializer = CustomerBatchSyncSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Invalid batch data',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            data = serializer.validated_data
            
            # Get tenant
            try:
                tenant = Tenant.objects.get(pk=data['tenantId'])
            except Tenant.DoesNotExist:
                return Response({
                    'success': False,
                    'message': 'Tenant not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Process each customer
            results = {
                'created': 0,
                'updated': 0,
                'errors': []
            }
            
            for customer_data in data['customers']:
                try:
                    # Generate username
                    username = f"{customer_data['email']}.{tenant.subdomain}"
                    
                    # Create or update TenantCustomer
                    tenant_customer, created = TenantCustomer.objects.update_or_create(
                        external_id=customer_data['customerId'],
                        tenant=tenant,
                        defaults={
                            'username': username,
                            'email': customer_data['email'],
                            'first_name': customer_data['firstName'],
                            'last_name': customer_data['lastName'],
                            'phone': customer_data.get('phone', ''),
                            'loyalty_points': customer_data.get('loyaltyPoints', 0),
                            'total_spent': customer_data.get('totalSpent', 0),
                            'visit_count': customer_data.get('visitCount', 0),
                            'is_active': True,
                            'role': 'customer',
                        }
                    )
                    
                    if created:
                        results['created'] += 1
                    else:
                        results['updated'] += 1
                        
                except Exception as e:
                    results['errors'].append({
                        'email': customer_data.get('email'),
                        'error': str(e)
                    })
            
            print(f"✅ Batch sync: {results['created']} created, {results['updated']} updated, {len(results['errors'])} errors")
            
            return Response({
                'success': True,
                'message': 'Batch sync completed',
                'results': results
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"❌ Error in batch sync: {str(e)}")
            return Response({
                'success': False,
                'message': f'Error processing batch: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)