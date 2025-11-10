# Generated migration to make customer_id nullable in TenantCustomer

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0002_initial'),  # Update this to your latest migration
    ]

    operations = [
        migrations.AlterField(
            model_name='tenantcustomer',
            name='customer',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='tenant_accounts',
                to='customers.customer'
            ),
        ),
    ]
