#!/usr/bin/env python
"""
Fix Business Owner Account
Run this in Django shell to properly set up accounts
"""

from customers.models import Customer, TenantCustomer
from tenants.models import Tenant
from django.contrib.auth.hashers import make_password

print("\n" + "=" * 70)
print("FIXING BUSINESS OWNER ACCOUNT")
print("=" * 70)

# Get tenant
tenant = Tenant.objects.get(slug='simifood')
print(f"\n✓ Tenant: {tenant.name}")

print("\n" + "-" * 70)
print("OPTION 1: Fix/Create owner@simifood.com account")
print("-" * 70)

# Delete old owner if exists (to start fresh)
Customer.objects.filter(email='owner@simifood.com').delete()
print("✓ Removed old owner account (if existed)")

# Create new owner - PROPERLY
owner = Customer.objects.create(
    email='owner@simifood.com',
    username='owner@simifood.com',  # Important!
    first_name='Business',
    last_name='Owner',
    is_active=True,
    password=make_password('password123')  # Proper password hashing
)
print(f"✓ Created owner: {owner.email}")
print(f"  - Username: {owner.username}")
print(f"  - Active: {owner.is_active}")
print(f"  - Password check: {owner.check_password('password123')}")

# Create TenantCustomer for owner
tc_owner = TenantCustomer.objects.create(
    customer=owner,
    tenant=tenant,
    role='owner',
    is_active=True,
    loyalty_points=0
)
print(f"✓ Created TenantCustomer for owner")
print(f"  - Role: {tc_owner.role}")
print(f"  - Is staff: {tc_owner.is_staff_member}")

print("\n" + "-" * 70)
print("OPTION 2: Check/Update john.customer@example.com")
print("-" * 70)

# Check John's account
john = Customer.objects.get(email='john.customer@example.com')
john_tc = TenantCustomer.objects.get(customer=john, tenant=tenant)

print(f"✓ John's account found: {john.email}")
print(f"  - Current role: {john_tc.role}")
print(f"  - Is staff: {john_tc.is_staff_member}")

# Ask if we should make John a manager too
print(f"\n  Current role is: '{john_tc.role}'")
if john_tc.role == 'customer':
    print("  → Making John a MANAGER so he can access business dashboard...")
    john_tc.role = 'manager'
    john_tc.save()
    print(f"  ✓ John's new role: {john_tc.role}")
    print(f"  ✓ John is now staff: {john_tc.is_staff_member}")
else:
    print(f"  → John is already staff (role: {john_tc.role})")

print("\n" + "=" * 70)
print("SETUP COMPLETE!")
print("=" * 70)

print("\nYou can now login with EITHER:\n")

print("OPTION 1 - Dedicated Owner Account:")
print("  URL: http://simifood.localhost:8000/login/")
print("  Email: owner@simifood.com")
print("  Password: password123")
print("  → Should see: BUSINESS DASHBOARD\n")

print("OPTION 2 - John (Manager):")
print("  URL: http://simifood.localhost:8000/login/")
print("  Email: john.customer@example.com")
print("  Password: password123")
print("  → Should see: BUSINESS DASHBOARD\n")

print("=" * 70)

# Verify both accounts can authenticate
print("\nTESTING AUTHENTICATION:\n")

from django.contrib.auth import authenticate

# Test owner
owner_auth = authenticate(username='owner@simifood.com', password='password123')
if owner_auth:
    print("✓ Owner authentication: SUCCESS")
else:
    print("✗ Owner authentication: FAILED")

# Test john
john_auth = authenticate(username='john.customer@example.com', password='password123')
if john_auth:
    print("✓ John authentication: SUCCESS")
else:
    print("✗ John authentication: FAILED")

print("\n" + "=" * 70 + "\n")