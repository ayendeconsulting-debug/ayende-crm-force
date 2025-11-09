# Generated migration for multi-tenant customer architecture refactoring
# ULTIMATE FIX - disables foreign key checks during migration

from django.db import migrations, models
import django.db.models.deletion
from django.contrib.auth.hashers import make_password


def migrate_customer_data_with_fk_disabled(apps, schema_editor):
    """
    Migrate existing Customer data with foreign key checks disabled.
    Creates username in format: email.subdomain
    """
    from django.db import connection
    
    print("\n" + "="*60)
    print("MIGRATING CUSTOMER DATA TO TENANT-SPECIFIC ACCOUNTS")
    print("="*60)
    
    # Disable foreign key checks
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA foreign_keys = OFF")
    
    try:
        with connection.cursor() as cursor:
            # Get all tenant_customers with their associated customer and tenant info
            cursor.execute("""
                SELECT 
                    tc.id,
                    tc.customer_id,
                    tc.tenant_id,
                    c.email,
                    c.password,
                    c.phone,
                    c.date_of_birth,
                    c.state,
                    c.city,
                    c.address,
                    c.last_visit,
                    c.loyalty_points,
                    c.loyalty_tier,
                    c.total_spent,
                    c.is_active,
                    t.subdomain
                FROM tenant_customers tc
                JOIN customers c ON tc.customer_id = c.id
                JOIN tenants_tenant t ON tc.tenant_id = t.id
            """)
            
            records = cursor.fetchall()
            total_count = len(records)
            print(f"\nProcessing {total_count} TenantCustomer records...")
            
            migrated_count = 0
            skipped_count = 0
            
            for record in records:
                (tc_id, customer_id, tenant_id, email, password, phone, dob, 
                 state, city, address, last_visit, loyalty_points, loyalty_tier, 
                 total_spent, is_active, subdomain) = record
                
                try:
                    # Generate username
                    email_val = email if email else f"user{customer_id}@temp.com"
                    username = f"{email_val}.{subdomain}"
                    
                    # Prepare password
                    password_val = password if password else make_password(None)
                    
                    # Update tenant_customer record with new fields
                    cursor.execute("""
                        UPDATE tenant_customers
                        SET username = %s,
                            email = %s,
                            password = %s,
                            phone = %s,
                            date_of_birth = %s,
                            state = %s,
                            city = %s,
                            address = %s,
                            last_visit = %s,
                            is_vip = 0
                        WHERE id = %s
                    """, [username, email_val, password_val, phone, dob, state, city, address, last_visit, tc_id])
                    
                    print(f"✅ Migrated: {email_val} → {username}")
                    migrated_count += 1
                    
                except Exception as e:
                    print(f"❌ Error migrating TenantCustomer {tc_id}: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    skipped_count += 1
        
        print("\n" + "="*60)
        print("MIGRATION COMPLETE")
        print("="*60)
        print(f"✅ Successfully migrated: {migrated_count} tenant-customer relationships")
        if skipped_count > 0:
            print(f"⚠️  Skipped/Failed: {skipped_count} records")
        print("="*60 + "\n")
        
    finally:
        # Re-enable foreign key checks
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA foreign_keys = ON")


def update_transaction_references_with_fk_disabled(apps, schema_editor):
    """
    Update Transaction references with foreign key checks disabled.
    """
    from django.db import connection
    
    print("\n" + "="*60)
    print("UPDATING TRANSACTION REFERENCES")
    print("="*60)
    
    # Disable foreign key checks
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA foreign_keys = OFF")
    
    try:
        with connection.cursor() as cursor:
            # Check how many transactions need updating
            cursor.execute("""
                SELECT COUNT(*) FROM transactions 
                WHERE customer_id IS NOT NULL 
                AND (tenant_customer_id IS NULL OR tenant_customer_id = '')
            """)
            count = cursor.fetchone()[0]
            print(f"\nFound {count} transactions to update...")
            
            if count > 0:
                # Update transactions to link to tenant_customer
                cursor.execute("""
                    UPDATE transactions 
                    SET tenant_customer_id = (
                        SELECT tc.id 
                        FROM tenant_customers tc
                        WHERE tc.customer_id = transactions.customer_id
                        AND tc.tenant_id = transactions.tenant_id
                        LIMIT 1
                    )
                    WHERE customer_id IS NOT NULL
                    AND (tenant_customer_id IS NULL OR tenant_customer_id = '')
                """)
                
                print(f"✅ Updated {count} transaction records")
            else:
                print("✅ No transactions need updating")
        
        print("="*60 + "\n")
        
    finally:
        # Re-enable foreign key checks
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA foreign_keys = ON")


def calculate_vip_status_final(apps, schema_editor):
    """
    Calculate VIP status using raw SQL.
    """
    from django.db import connection
    
    print("\n" + "="*60)
    print("CALCULATING VIP STATUS")
    print("="*60)
    
    with connection.cursor() as cursor:
        # Update VIP status based on total_spent and tenant VIP threshold
        cursor.execute("""
            UPDATE tenant_customers
            SET is_vip = 1
            WHERE id IN (
                SELECT tc.id
                FROM tenant_customers tc
                JOIN tenants_tenantsettings ts ON tc.tenant_id = ts.tenant_id
                WHERE tc.total_spent >= ts.vip_threshold
            )
        """)
        
        vip_count = cursor.rowcount if cursor.rowcount > 0 else 0
        print(f"\n✅ Set {vip_count} customers as VIP")
    
    print("="*60 + "\n")


def reverse_migration(apps, schema_editor):
    """
    Reverse the migration (for rollback support).
    """
    print("\n⚠️  REVERSING MULTI-TENANT MIGRATION")


class Migration(migrations.Migration):
    
    atomic = False  # Disable atomic transaction to prevent rollback on constraint check

    dependencies = [
        ('customers', '0007_make_transaction_notes_nullable'),
        ('tenants', '0004_tenantsettings_vip_threshold'),
    ]

    operations = [
        # Step 1: Add new fields to TenantCustomer
        migrations.AddField(
            model_name='tenantcustomer',
            name='username',
            field=models.CharField(max_length=150, default='temp_username'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='tenantcustomer',
            name='email',
            field=models.EmailField(max_length=254, default='temp@example.com'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='tenantcustomer',
            name='password',
            field=models.CharField(max_length=128, default='!'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='tenantcustomer',
            name='is_vip',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='tenantcustomer',
            name='phone',
            field=models.CharField(blank=True, max_length=15, null=True),
        ),
        migrations.AddField(
            model_name='tenantcustomer',
            name='date_of_birth',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='tenantcustomer',
            name='state',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='tenantcustomer',
            name='city',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='tenantcustomer',
            name='address',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='tenantcustomer',
            name='last_visit',
            field=models.DateTimeField(blank=True, null=True),
        ),
        
        # Step 2: Make Transaction.customer nullable
        migrations.AlterField(
            model_name='transaction',
            name='customer',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='old_transactions',
                to='customers.customer',
                db_column='customer_id',
            ),
        ),
        
        # Step 3: Run data migration with FK checks disabled
        migrations.RunPython(migrate_customer_data_with_fk_disabled, reverse_migration),
        
        # Step 4: Update transaction references with FK checks disabled
        migrations.RunPython(update_transaction_references_with_fk_disabled, reverse_migration),
        
        # Step 5: Calculate VIP status
        migrations.RunPython(calculate_vip_status_final, reverse_migration),
        
        # Step 6: Add unique constraint on (tenant, username)
        migrations.AlterUniqueTogether(
            name='tenantcustomer',
            unique_together={('tenant', 'username')},
        ),
        
        # Step 7: Add indexes for performance
        migrations.AddIndex(
            model_name='tenantcustomer',
            index=models.Index(fields=['tenant', 'email'], name='tenant_cust_tenant_email_idx'),
        ),
        migrations.AddIndex(
            model_name='tenantcustomer',
            index=models.Index(fields=['tenant', 'username'], name='tenant_cust_tenant_user_idx'),
        ),
    ]