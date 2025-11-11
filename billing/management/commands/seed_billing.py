from django.core.management.base import BaseCommand
from billing.models import SubscriptionPlan, ProfessionalFeeType
from decimal import Decimal

class Command(BaseCommand):
    help = 'Seed billing data with subscription plans and fee types'

    def handle(self, *args, **kwargs):
        # Create subscription plans
        plans = [
            {
                'name': 'Starter',
                'description': 'Perfect for small businesses just getting started',
                'billing_cycle': 'monthly',
                'price': Decimal('49.00'),
                'max_customers': 100,
                'max_transactions_per_month': 500,
                'max_staff_users': 3,
                'has_analytics': True,
                'has_api_access': False,
                'has_custom_branding': False,
                'has_priority_support': False,
                'trial_days': 14,
            },
            {
                'name': 'Starter Annual',
                'description': 'Starter plan billed annually (save 17%)',
                'billing_cycle': 'annual',
                'price': Decimal('490.00'),
                'max_customers': 100,
                'max_transactions_per_month': 500,
                'max_staff_users': 3,
                'has_analytics': True,
                'has_api_access': False,
                'has_custom_branding': False,
                'has_priority_support': False,
                'trial_days': 14,
            },
            {
                'name': 'Professional',
                'description': 'For growing businesses that need more power',
                'billing_cycle': 'monthly',
                'price': Decimal('149.00'),
                'max_customers': 500,
                'max_transactions_per_month': 2000,
                'max_staff_users': 10,
                'has_analytics': True,
                'has_api_access': True,
                'has_custom_branding': True,
                'has_priority_support': False,
                'trial_days': 14,
            },
            {
                'name': 'Professional Annual',
                'description': 'Professional plan billed annually (save 17%)',
                'billing_cycle': 'annual',
                'price': Decimal('1490.00'),
                'max_customers': 500,
                'max_transactions_per_month': 2000,
                'max_staff_users': 10,
                'has_analytics': True,
                'has_api_access': True,
                'has_custom_branding': True,
                'has_priority_support': False,
                'trial_days': 14,
            },
            {
                'name': 'Enterprise',
                'description': 'Unlimited everything for large operations',
                'billing_cycle': 'monthly',
                'price': Decimal('499.00'),
                'max_customers': 999999,
                'max_transactions_per_month': 999999,
                'max_staff_users': 999999,
                'has_analytics': True,
                'has_api_access': True,
                'has_custom_branding': True,
                'has_priority_support': True,
                'trial_days': 30,
            },
            {
                'name': 'Enterprise Annual',
                'description': 'Enterprise plan billed annually (save 17%)',
                'billing_cycle': 'annual',
                'price': Decimal('4990.00'),
                'max_customers': 999999,
                'max_transactions_per_month': 999999,
                'max_staff_users': 999999,
                'has_analytics': True,
                'has_api_access': True,
                'has_custom_branding': True,
                'has_priority_support': True,
                'trial_days': 30,
            },
        ]

        for plan_data in plans:
            plan, created = SubscriptionPlan.objects.get_or_create(
                name=plan_data['name'],
                billing_cycle=plan_data['billing_cycle'],
                defaults=plan_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created plan: {plan.name}'))
            else:
                self.stdout.write(f'Plan already exists: {plan.name}')

        # Create professional fee types
        fee_types = [
            {
                'name': 'Setup & Onboarding',
                'description': 'Initial setup and onboarding session',
                'default_amount': Decimal('299.00'),
            },
            {
                'name': 'Training Session',
                'description': 'Staff training session (per hour)',
                'default_amount': Decimal('150.00'),
            },
            {
                'name': 'Custom Development',
                'description': 'Custom feature development (per hour)',
                'default_amount': Decimal('200.00'),
            },
            {
                'name': 'Technical Support Package',
                'description': 'Priority technical support package',
                'default_amount': Decimal('500.00'),
            },
            {
                'name': 'Data Migration',
                'description': 'Migrate data from existing system',
                'default_amount': Decimal('750.00'),
            },
            {
                'name': 'Consulting',
                'description': 'Business consulting (per hour)',
                'default_amount': Decimal('175.00'),
            },
        ]

        for fee_data in fee_types:
            fee_type, created = ProfessionalFeeType.objects.get_or_create(
                name=fee_data['name'],
                defaults=fee_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created fee type: {fee_type.name}'))
            else:
                self.stdout.write(f'Fee type already exists: {fee_type.name}')

        self.stdout.write(self.style.SUCCESS('Billing seed data created successfully!'))