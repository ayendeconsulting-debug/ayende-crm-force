# Generated migration for adding platform admin functionality
# Place this file in: customers/migrations/0004_add_platform_admin_flag.py

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0003_make_customer_nullable'),
    ]

    operations = [
        # Step 1: Make customer and tenant nullable (for platform admins)
        migrations.AlterField(
            model_name='tenantcustomer',
            name='customer',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.CASCADE,
                related_name='tenant_accounts',
                to='customers.customer'
            ),
        ),
        migrations.AlterField(
            model_name='tenantcustomer',
            name='tenant',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.CASCADE,
                related_name='tenant_customers',
                to='tenants.tenant'
            ),
        ),
        
        # Step 2: Add is_platform_admin field
        migrations.AddField(
            model_name='tenantcustomer',
            name='is_platform_admin',
            field=models.BooleanField(
                default=False,
                help_text='Designates whether this user is a platform administrator with cross-tenant access. Platform admins can manage all tenants and access the main admin panel at staging.ayendecx.com/admin/'
            ),
        ),
        
        # Step 3: Add index for is_platform_admin
        migrations.AddIndex(
            model_name='tenantcustomer',
            index=models.Index(fields=['is_platform_admin'], name='customers_t_is_plat_idx'),
        ),
        
        # Step 4: Remove old unique_together constraint
        migrations.AlterUniqueTogether(
            name='tenantcustomer',
            unique_together=set(),
        ),
        
        # Step 5: Add new constraint for username uniqueness per tenant
        migrations.AddConstraint(
            model_name='tenantcustomer',
            constraint=models.UniqueConstraint(
                condition=models.Q(('tenant__isnull', False)),
                fields=('tenant', 'username'),
                name='unique_username_per_tenant'
            ),
        ),
        
        # Step 6: Add constraint for platform admin username uniqueness
        migrations.AddConstraint(
            model_name='tenantcustomer',
            constraint=models.UniqueConstraint(
                condition=models.Q(('is_platform_admin', True)),
                fields=('username',),
                name='unique_platform_admin_username'
            ),
        ),
    ]
