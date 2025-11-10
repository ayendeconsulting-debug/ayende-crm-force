"""
Serializers for POS Integration Sync Operations
Handles transaction and customer data from POS system
"""

from rest_framework import serializers


class TransactionItemSyncSerializer(serializers.Serializer):
    """Serializer for transaction line items"""
    productId = serializers.UUIDField()
    name = serializers.CharField(max_length=255)
    quantity = serializers.IntegerField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    total = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)


class TransactionSyncSerializer(serializers.Serializer):
    """
    Serializer for transaction sync from POS
    Validates incoming transaction data structure
    """
    transactionId = serializers.UUIDField()
    tenantId = serializers.CharField(max_length=20)
    customerId = serializers.UUIDField()
    customerEmail = serializers.EmailField()
    
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    tax = serializers.DecimalField(max_digits=10, decimal_places=2)
    total = serializers.DecimalField(max_digits=10, decimal_places=2)
    
    paymentMethod = serializers.ChoiceField(
        choices=['CASH', 'CARD', 'MOBILE_MONEY', 'BANK_TRANSFER', 'OTHER']
    )
    
    pointsEarned = serializers.IntegerField(default=0)
    pointsRedeemed = serializers.IntegerField(default=0)
    
    items = TransactionItemSyncSerializer(many=True)
    timestamp = serializers.DateTimeField()
    
    # Optional fields
    notes = serializers.CharField(required=False, allow_blank=True)
    receiptNumber = serializers.CharField(required=False, allow_blank=True)


class CustomerSyncSerializer(serializers.Serializer):
    """
    Serializer for customer sync from POS
    Validates incoming customer data structure
    """
    customerId = serializers.UUIDField()
    tenantId = serializers.CharField(max_length=20)
    
    email = serializers.EmailField()
    firstName = serializers.CharField(max_length=100)
    lastName = serializers.CharField(max_length=100)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    
    # Address fields
    address = serializers.CharField(required=False, allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    postalCode = serializers.CharField(max_length=20, required=False, allow_blank=True)
    country = serializers.CharField(max_length=100, required=False, allow_blank=True)
    
    # Profile fields
    dateOfBirth = serializers.DateField(required=False, allow_null=True)
    marketingOptIn = serializers.BooleanField(default=False)
    
    # Loyalty fields (from POS)
    loyaltyPoints = serializers.IntegerField(default=0)
    loyaltyTier = serializers.ChoiceField(
        choices=['BRONZE', 'SILVER', 'GOLD', 'PLATINUM'],
        required=False
    )
    totalSpent = serializers.DecimalField(max_digits=10, decimal_places=2, default=0)
    visitCount = serializers.IntegerField(default=0)
    
    # Timestamps
    memberSince = serializers.DateTimeField(required=False)
    lastVisit = serializers.DateTimeField(required=False, allow_null=True)
    updatedAt = serializers.DateTimeField()


class CustomerBatchSyncSerializer(serializers.Serializer):
    """
    Serializer for batch customer sync
    """
    customers = CustomerSyncSerializer(many=True)
    tenantId = serializers.CharField(max_length=20)


class SyncResponseSerializer(serializers.Serializer):
    """
    Standard response format for sync operations
    """
    success = serializers.BooleanField()
    message = serializers.CharField()
    entityId = serializers.CharField(required=False)
    errors = serializers.DictField(required=False)
