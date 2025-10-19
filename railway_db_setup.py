#!/usr/bin/env python
"""
Railway Database Setup Script
Quick setup for Ayende CX on Railway PostgreSQL

Usage:
    railway run python railway_db_setup.py
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.db import transaction, connection
from tenants.models import Tenant, TenantSettings
from customers.models import TenantCustomer
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta

print("=" * 70)
print("RAILWAY DATABASE SETUP - AYENDE CX")
print("=" * 70)
print()

Customer = get_user_model()

# Colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def success(msg):
    print(f"{GREEN}✓{RESET} {msg}")

def error(msg):
    print(f"{RED}✗{RESET} {msg}")

def info(msg):
    print(f"{BLUE}ℹ{RESET} {msg}")

def warning(msg):
    print(f"{YELLOW}⚠{RESET} {msg}")

# Check database connection
print("CHECKING DATABASE CONNECTION")
print("-" * 70)
try:
    with connection.cursor() as cursor:
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        success(f"Connected to PostgreSQL")
        info(f"Version: {version[0][:50]}...")
except Exception as e:
    error(f"Database connection failed: {e}")
    exit(1)

print()

# Run migrations
print("RUNNING MIGRATIONS")
print("-" * 70)
try:
    from django.core.management import call_command
    call_command('migrate', '--noinput')
    success("All migrations applied")
except Exception as e:
    error(f"Migration failed: {e}")
    exit(1)

print()

# Create superuser
print("CREATING SUPERUSER")
print("-" * 70)

superuser_exists = Customer.objects.filter(is_superuser=True).exists()

if not superuser_exists:
    try:
        # Use environment variables or defaults
        admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
        admin_email = os.environ.get('ADMIN_EMAIL', 'admin@ayende.com')
        admin_password = os.environ.get('ADMIN_PASSWORD', 'changeme123!')
        
        superuser = Customer.objects.create_superuser(
            username=admin_username,
            email=admin_email,
            password=admin_password,
            first_name="System",
            last_name="Administrator"
        )
        success(f"Superuser created: {admin_username}")
        warning(f"⚠ Default password: {admin_password}")
        warning("⚠ CHANGE THIS PASSWORD IMMEDIATELY!")
        info(f"Admin URL: https://your-app.railway.app/admin/")
    except Exception as e:
        error(f"Failed to create superuser: {e}")
else:
    info("Superuser already exists")

print()

# Create production tenant
print("CREATING PRODUCTION TENANT")
print("-" * 70)

create_tenant = input("Create a production tenant? (y/n, default: y): ").strip().lower()

if create_tenant != 'n':
    tenant_name = input("Enter business name (default: My Business): ").strip()
    if not tenant_name:
        tenant_name = "My Business"
    
    tenant_slug = input("Enter subdomain slug (default: mybusiness): ").strip()
    if not tenant_slug:
        tenant_slug = "mybusiness"
    
    # Convert to lowercase and remove spaces
    tenant_slug = tenant_slug.lower().replace(' ', '')
    
    currency = input("Enter currency code (USD, NGN, GBP, EUR, default: USD): ").strip().upper()
    if not currency:
        currency = "USD"
    
    try:
        with transaction.atomic():
            superuser = Customer.objects.filter(is_superuser=True).first()
            
            tenant, created = Tenant.objects.get_or_create(
                slug=tenant_slug,
                defaults={
                    'name': tenant_name,
                    'owner': superuser,
                    'currency': currency,
                    'subscription_status': 'trial',
                    'trial_ends_at': timezone.now() + timedelta(days=30),
                    'is_active': True
                }
            )
            
            if created:
                success(f"Created tenant: {tenant.name}")
                success(f"Slug: {tenant.slug}")
                success(f"Currency: {tenant.currency}")
                
                # Create settings
                settings, _ = TenantSettings.objects.get_or_create(
                    tenant=tenant,
                    defaults={
                        'allow_customer_registration': True,
                        'require_email_verification': False,
                        'max_customers': 10000,
                        'enable_loyalty_points': True,
                        'points_per_dollar': Decimal('1.00'),
                        'notification_email': f'support@{tenant_slug}.com',
                    }
                )
                success("Created tenant settings")
                
                info(f"Customer registration URL: https://your-app.railway.app/register/?tenant={tenant_slug}")
            else:
                warning(f"Tenant '{tenant_slug}' already exists")
                
    except Exception as e:
        error(f"Failed to create tenant: {e}")
        import traceback
        traceback.print_exc()

print()

# Collect static files
print("COLLECTING STATIC FILES")
print("-" * 70)
try:
    from django.core.management import call_command
    call_command('collectstatic', '--noinput', '--clear')
    success("Static files collected")
except Exception as e:
    warning(f"Static files collection issue: {e}")
    info("This might be normal if static files don't exist yet")

print()

# Database statistics
print("DATABASE STATISTICS")
print("-" * 70)
try:
    tenant_count = Tenant.objects.count()
    customer_count = Customer.objects.count()
    settings_count = TenantSettings.objects.count()
    
    success(f"Tenants: {tenant_count}")
    success(f"Customers: {customer_count}")
    success(f"Tenant Settings: {settings_count}")
except Exception as e:
    error(f"Failed to get statistics: {e}")

print()

# Check for missing settings
print("CHECKING TENANT SETTINGS")
print("-" * 70)
try:
    tenants_without_settings = []
    for tenant in Tenant.objects.all():
        if not hasattr(tenant, 'settings'):
            tenants_without_settings.append(tenant)
            # Auto-create
            TenantSettings.objects.create(tenant=tenant)
            success(f"Created missing settings for: {tenant.name}")
    
    if not tenants_without_settings:
        success("All tenants have settings")
except Exception as e:
    error(f"Settings check failed: {e}")

print()

# Summary
print("=" * 70)
print("RAILWAY DATABASE SETUP COMPLETE")
print("=" * 70)
print()

print("NEXT STEPS:")
print("-" * 70)
print()
print("1. Access your admin panel:")
print("   https://your-app.railway.app/admin/")
print()
print("2. Login credentials:")
admin = Customer.objects.filter(is_superuser=True).first()
if admin:
    print(f"   Username: {admin.username}")
    print(f"   Password: (check environment variables or use default)")
print()
print("3. IMPORTANT SECURITY:")
print("   - Change admin password immediately")
print("   - Set secure SECRET_KEY in Railway variables")
print("   - Review ALLOWED_HOSTS setting")
print()
print("4. Configure your tenant:")
print("   - Go to Admin → Tenants")
print("   - Update tenant settings")
print("   - Configure loyalty points")
print()
print("5. Test customer registration:")
tenants = Tenant.objects.all()
if tenants:
    first_tenant = tenants[0]
    print(f"   https://your-app.railway.app/register/?tenant={first_tenant.slug}")
print()
print("6. Environment Variables to Set (Railway Dashboard):")
print("   - SECRET_KEY=<secure-random-key>")
print("   - DEBUG=False")
print("   - ALLOWED_HOSTS=.railway.app")
print("   - EMAIL_HOST=smtp.gmail.com (for email features)")
print()
print("=" * 70)
print()

# Generate secure secret key
try:
    from django.core.management.utils import get_random_secret_key
    print("GENERATE NEW SECRET_KEY:")
    print("-" * 70)
    new_key = get_random_secret_key()
    print(f"{new_key}")
    print()
    print("Copy this and add to Railway environment variables:")
    print(f"SECRET_KEY={new_key}")
    print()
except:
    pass

print("Setup complete! Your CRM is ready to use.")
