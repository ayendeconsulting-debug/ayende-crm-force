from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
       ('tenants', '0003_tenantsettings_birthday_bonus_enabled_and_more'),
    ]
    
    operations = [
        migrations.RunSQL(
            sql="""
                -- Drop old incorrect FK constraint (if it exists)
                ALTER TABLE tenants_tenant 
                DROP CONSTRAINT IF EXISTS tenants_tenant_owner_id_d1114a4f_fk_customers_id;
                
                -- Add correct FK constraint pointing to tenant_customers
                ALTER TABLE tenants_tenant
                ADD CONSTRAINT tenants_tenant_owner_id_fk_tenant_customers
                FOREIGN KEY (owner_id) 
                REFERENCES tenant_customers(id)
                ON DELETE SET NULL;
            """,
            reverse_sql="""
                ALTER TABLE tenants_tenant
                DROP CONSTRAINT IF EXISTS tenants_tenant_owner_id_fk_tenant_customers;
            """
        ),
    ]