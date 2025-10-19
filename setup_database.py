#!/usr/bin/env python
"""
Database Setup Script for Ayende CX Multi-Tenant CRM
Creates all necessary tables and initial data

Usage:
    python setup_database.py
"""

import os
import django
import sys

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.db import transaction
from tenants.models import Tenant, TenantSettings
from customers.models import Customer, TenantCustomer
from dashboard.models import Transaction
from notifications.models import Notification, NotificationRecipient
from rewards.models import Reward, Redemption
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

print("=" * 70)
print("AYENDE CX - DATABASE SETUP SCRIPT")
print("=" * 70)
print()

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def success(msg):
    print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")

def error(msg):
    print(f"{Colors.RED}✗{Colors.RESET} {msg}")

def info(msg):
    print(f"{Colors.BLUE}ℹ{Colors.RESET} {msg}")

def warning(msg):
    print(f"{Colors.YELLOW}⚠{Colors.RESET} {msg}")

# Step 1: Run Migrations
print("STEP 1: Running Database Migrations")
print("-" * 70)

try:
    from django.core.management import call_command
    
    info("Checking for pending migrations...")
    call_command('migrate', '--noinput')
    success("All migrations applied successfully")
except Exception as e:
    error(f"Migration failed: {e}")
    sys.exit(1)

print()

# Step 2: Create Superuser
print("STEP 2: Creating Superuser")
print("-" * 70)

Customer = get_user_model()

superuser_email = input("Enter superuser email (default: admin@ayende.com): ").strip()
if not superuser_email:
    superuser_email = "admin@ayende.com"

superuser_username = input("Enter superuser username (default: admin): ").strip()
if not superuser_username:
    superuser_username = "admin"

superuser_password = input("Enter superuser password (default: admin123): ").strip()
if not superuser_password:
    superuser_password = "admin123"

try:
    if not Customer.objects.filter(username=superuser_username).exists():
        superuser = Customer.objects.create_superuser(
            username=superuser_username,
            email=superuser_email,
            password=superuser_password,
            first_name="System",
            last_name="Administrator"
        )
        success(f"Superuser created: {superuser_username}")
        info(f"Login at: /admin/ with username '{superuser_username}'")
    else:
        warning(f"Superuser '{superuser_username}' already exists")
except Exception as e:
    error(f"Failed to create superuser: {e}")

print()

# Step 3: Create Sample Tenants
print("STEP 3: Creating Sample Tenants")
print("-" * 70)

create_samples = input("Create sample tenants and data? (y/n, default: y): ").strip().lower()
if create_samples != 'n':
    try:
        with transaction.atomic():
            # Tenant 1: Restaurant
            if not Tenant.objects.filter(slug='simifood').exists():
                tenant1 = Tenant.objects.create(
                    name="Simi's Food Place",
                    slug="simifood",
                    owner=superuser,
                    currency="NGN",
                    subscription_status="trial",
                    trial_ends_at=timezone.now() + timedelta(days=30),
                    is_active=True
                )
                success(f"Created tenant: {tenant1.name} (slug: simifood)")
                
                # Create settings for tenant1
                settings1 = TenantSettings.objects.get_or_create(
                    tenant=tenant1,
                    defaults={
                        'allow_customer_registration': True,
                        'require_email_verification': False,
                        'max_customers': 1000,
                        'enable_loyalty_points': True,
                        'points_per_dollar': Decimal('1.00'),
                        'notification_email': 'notifications@simifood.com',
                        'business_hours': '9:00 AM - 9:00 PM',
                    }
                )[0]
                success("Created tenant settings for Simi's Food Place")
            else:
                tenant1 = Tenant.objects.get(slug='simifood')
                warning("Tenant 'simifood' already exists")

            # Tenant 2: Retail Store
            if not Tenant.objects.filter(slug='techstore').exists():
                tenant2 = Tenant.objects.create(
                    name="Tech Store Pro",
                    slug="techstore",
                    owner=superuser,
                    currency="USD",
                    subscription_status="trial",
                    trial_ends_at=timezone.now() + timedelta(days=30),
                    is_active=True
                )
                success(f"Created tenant: {tenant2.name} (slug: techstore)")
                
                # Create settings for tenant2
                settings2 = TenantSettings.objects.get_or_create(
                    tenant=tenant2,
                    defaults={
                        'allow_customer_registration': True,
                        'require_email_verification': True,
                        'max_customers': 5000,
                        'enable_loyalty_points': True,
                        'points_per_dollar': Decimal('2.00'),
                        'notification_email': 'support@techstore.com',
                        'business_hours': '10:00 AM - 8:00 PM',
                    }
                )[0]
                success("Created tenant settings for Tech Store Pro")
            else:
                tenant2 = Tenant.objects.get(slug='techstore')
                warning("Tenant 'techstore' already exists")

            # Tenant 3: Gym/Fitness
            if not Tenant.objects.filter(slug='fitnesshub').exists():
                tenant3 = Tenant.objects.create(
                    name="Fitness Hub",
                    slug="fitnesshub",
                    owner=superuser,
                    currency="GBP",
                    subscription_status="active",
                    is_active=True
                )
                success(f"Created tenant: {tenant3.name} (slug: fitnesshub)")
                
                # Create settings for tenant3
                settings3 = TenantSettings.objects.get_or_create(
                    tenant=tenant3,
                    defaults={
                        'allow_customer_registration': True,
                        'require_email_verification': False,
                        'max_customers': 500,
                        'enable_loyalty_points': True,
                        'points_per_dollar': Decimal('0.50'),
                        'notification_email': 'members@fitnesshub.com',
                        'business_hours': '6:00 AM - 10:00 PM',
                    }
                )[0]
                success("Created tenant settings for Fitness Hub")
            else:
                tenant3 = Tenant.objects.get(slug='fitnesshub')
                warning("Tenant 'fitnesshub' already exists")

    except Exception as e:
        error(f"Failed to create sample tenants: {e}")
        import traceback
        traceback.print_exc()

    print()

    # Step 4: Create Sample Customers
    print("STEP 4: Creating Sample Customers")
    print("-" * 70)

    try:
        with transaction.atomic():
            # Get tenants
            tenant1 = Tenant.objects.get(slug='simifood')
            
            # Customer 1 for Simi's Food Place
            if not Customer.objects.filter(username='john_customer').exists():
                customer1 = Customer.objects.create_user(
                    username='john_customer',
                    email='john@example.com',
                    password='customer123',
                    first_name='John',
                    last_name='Doe',
                    phone_number='+1234567890',
                    date_of_birth='1990-05-15',
                )
                success(f"Created customer: {customer1.get_full_name()}")
                
                # Link to tenant
                tenant_customer1 = TenantCustomer.objects.create(
                    tenant=tenant1,
                    customer=customer1,
                    loyalty_points=150,
                    total_spent=Decimal('1500.00'),
                    visit_count=12
                )
                success(f"Linked {customer1.username} to {tenant1.name}")
            else:
                customer1 = Customer.objects.get(username='john_customer')
                warning("Customer 'john_customer' already exists")

            # Customer 2 for Simi's Food Place
            if not Customer.objects.filter(username='jane_customer').exists():
                customer2 = Customer.objects.create_user(
                    username='jane_customer',
                    email='jane@example.com',
                    password='customer123',
                    first_name='Jane',
                    last_name='Smith',
                    phone_number='+1234567891',
                    date_of_birth='1992-08-20',
                )
                success(f"Created customer: {customer2.get_full_name()}")
                
                # Link to tenant
                tenant_customer2 = TenantCustomer.objects.create(
                    tenant=tenant1,
                    customer=customer2,
                    loyalty_points=280,
                    total_spent=Decimal('2800.00'),
                    visit_count=25
                )
                success(f"Linked {customer2.username} to {tenant1.name}")
            else:
                customer2 = Customer.objects.get(username='jane_customer')
                warning("Customer 'jane_customer' already exists")

    except Exception as e:
        error(f"Failed to create sample customers: {e}")
        import traceback
        traceback.print_exc()

    print()

    # Step 5: Create Sample Transactions
    print("STEP 5: Creating Sample Transactions")
    print("-" * 70)

    try:
        with transaction.atomic():
            tenant1 = Tenant.objects.get(slug='simifood')
            customer1 = Customer.objects.get(username='john_customer')
            customer2 = Customer.objects.get(username='jane_customer')
            
            # Transactions for customer1
            transactions_data = [
                {
                    'customer': customer1,
                    'amount': Decimal('125.50'),
                    'description': 'Lunch order - Jollof Rice Special',
                    'days_ago': 2
                },
                {
                    'customer': customer1,
                    'amount': Decimal('85.00'),
                    'description': 'Breakfast order - Continental',
                    'days_ago': 5
                },
                {
                    'customer': customer2,
                    'amount': Decimal('200.00'),
                    'description': 'Family dinner package',
                    'days_ago': 1
                },
                {
                    'customer': customer2,
                    'amount': Decimal('150.00'),
                    'description': 'Catering order',
                    'days_ago': 7
                },
            ]
            
            for trans_data in transactions_data:
                tenant_customer = TenantCustomer.objects.get(
                    tenant=tenant1,
                    customer=trans_data['customer']
                )
                
                transaction_obj = Transaction.objects.create(
                    tenant_customer=tenant_customer,
                    transaction_type='purchase',
                    amount=trans_data['amount'],
                    points_earned=int(trans_data['amount']),  # 1 point per currency unit
                    description=trans_data['description'],
                    created_at=timezone.now() - timedelta(days=trans_data['days_ago'])
                )
                success(f"Created transaction: {trans_data['description']} - {trans_data['amount']}")

    except Exception as e:
        error(f"Failed to create sample transactions: {e}")
        import traceback
        traceback.print_exc()

    print()

    # Step 6: Create Sample Rewards
    print("STEP 6: Creating Sample Rewards")
    print("-" * 70)

    try:
        with transaction.atomic():
            tenant1 = Tenant.objects.get(slug='simifood')
            
            rewards_data = [
                {
                    'name': 'Free Drink',
                    'description': 'Get a free drink of your choice',
                    'points_required': 50,
                    'value': Decimal('5.00'),
                },
                {
                    'name': '10% Discount',
                    'description': '10% off your next purchase',
                    'points_required': 100,
                    'value': Decimal('0.00'),
                },
                {
                    'name': 'Free Meal',
                    'description': 'Complimentary meal (up to $15 value)',
                    'points_required': 200,
                    'value': Decimal('15.00'),
                },
                {
                    'name': 'VIP Card',
                    'description': 'VIP membership for 1 month',
                    'points_required': 500,
                    'value': Decimal('50.00'),
                },
            ]
            
            for reward_data in rewards_data:
                reward, created = Reward.objects.get_or_create(
                    tenant=tenant1,
                    name=reward_data['name'],
                    defaults={
                        'description': reward_data['description'],
                        'points_required': reward_data['points_required'],
                        'value': reward_data['value'],
                        'is_active': True,
                        'valid_from': timezone.now(),
                        'valid_until': timezone.now() + timedelta(days=365),
                    }
                )
                if created:
                    success(f"Created reward: {reward.name} ({reward.points_required} points)")
                else:
                    warning(f"Reward '{reward.name}' already exists")

    except Exception as e:
        error(f"Failed to create sample rewards: {e}")
        import traceback
        traceback.print_exc()

    print()

    # Step 7: Create Sample Notifications
    print("STEP 7: Creating Sample Notifications")
    print("-" * 70)

    try:
        with transaction.atomic():
            tenant1 = Tenant.objects.get(slug='simifood')
            
            # Create a tenant-wide notification
            notification = Notification.objects.create(
                tenant=tenant1,
                title="Welcome to Simi's Food Place!",
                message="Thank you for joining our loyalty program. Earn points with every purchase!",
                notification_type='promotion',
                is_active=True,
            )
            success(f"Created notification: {notification.title}")
            
            # Send to all customers
            tenant_customers = TenantCustomer.objects.filter(tenant=tenant1)
            for tc in tenant_customers:
                NotificationRecipient.objects.create(
                    notification=notification,
                    tenant_customer=tc,
                    is_read=False,
                )
            success(f"Sent notification to {tenant_customers.count()} customers")

    except Exception as e:
        error(f"Failed to create sample notifications: {e}")
        import traceback
        traceback.print_exc()

else:
    info("Skipping sample data creation")

print()

# Summary
print("=" * 70)
print("DATABASE SETUP COMPLETE")
print("=" * 70)
print()

print("SUMMARY:")
print("-" * 70)

try:
    tenant_count = Tenant.objects.count()
    customer_count = Customer.objects.count()
    transaction_count = Transaction.objects.count()
    reward_count = Reward.objects.count()
    notification_count = Notification.objects.count()
    
    success(f"Tenants created: {tenant_count}")
    success(f"Customers created: {customer_count}")
    success(f"Transactions created: {transaction_count}")
    success(f"Rewards created: {reward_count}")
    success(f"Notifications created: {notification_count}")
except Exception as e:
    error(f"Failed to generate summary: {e}")

print()
print("NEXT STEPS:")
print("-" * 70)
print("1. Access admin panel: http://localhost:8000/admin/")
print(f"   Username: {superuser_username}")
print(f"   Password: {superuser_password}")
print()
print("2. Sample tenants created:")
print("   - simifood.localhost:8000")
print("   - techstore.localhost:8000")
print("   - fitnesshub.localhost:8000")
print()
print("3. Sample customers:")
print("   - Username: john_customer, Password: customer123")
print("   - Username: jane_customer, Password: customer123")
print()
print("4. Start development server:")
print("   python manage.py runserver")
print()
print("=" * 70)
