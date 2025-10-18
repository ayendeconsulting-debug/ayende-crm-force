"""
Create this file: customers/management/commands/recalculate_stats.py

This command will recalculate all customer statistics from transactions.
Run with: python manage.py recalculate_stats
"""

from django.core.management.base import BaseCommand
from customers.models import TenantCustomer, Transaction
from django.db.models import Sum, Count


class Command(BaseCommand):
    help = 'Recalculate customer statistics from transactions'

    def handle(self, *args, **options):
        self.stdout.write('Recalculating customer statistics...')
        
        # Get all tenant-customer relationships
        tenant_customers = TenantCustomer.objects.all()
        
        updated_count = 0
        for tc in tenant_customers:
            # Get all completed purchase transactions for this customer
            transactions = Transaction.objects.filter(
                tenant_customer=tc,
                status='completed',
                transaction_type='purchase'
            )
            
            # Calculate totals
            stats = transactions.aggregate(
                total_spent=Sum('total'),
                purchase_count=Count('id'),
                points_earned=Sum('points_earned')
            )
            
            # Update the tenant_customer record
            if hasattr(tc, 'total_spent'):
                tc.total_spent = stats['total_spent'] or 0
            
            tc.total_purchases = stats['purchase_count'] or 0
            tc.loyalty_points = stats['points_earned'] or 0
            
            # Get last purchase date
            last_transaction = transactions.order_by('-transaction_date').first()
            if last_transaction:
                tc.last_purchase_date = last_transaction.transaction_date.date()
            
            tc.save()
            updated_count += 1
            
            self.stdout.write(
                f'  Updated {tc.customer.email} @ {tc.tenant.name}: '
                f'{tc.total_purchases} purchases, ${stats["total_spent"] or 0}'
            )
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully updated {updated_count} customer records!')
        )king