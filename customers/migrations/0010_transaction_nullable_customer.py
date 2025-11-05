# customers/migrations/0010_transaction_nullable_customer.py
"""
Migration to make customer and tenant_customer fields nullable in Transaction model.
This allows anonymous transactions (walk-in customers) to be tracked without customer linkage.

IMPORTANT: This migration should be placed in customers/migrations/ directory
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0009_calculate_initial_vip_status'),
        ('tenants', '0001_initial'),
    ]

    operations = [
        # Make customer field nullable
        migrations.AlterField(
            model_name='transaction',
            name='customer',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='transactions',
                to='customers.customer'
            ),
        ),
        # Make tenant_customer field nullable
        migrations.AlterField(
            model_name='transaction',
            name='tenant_customer',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='transactions',
                to='customers.tenantcustomer'
            ),
        ),
        # Add is_anonymous flag for easy filtering
        migrations.AddField(
            model_name='transaction',
            name='is_anonymous',
            field=models.BooleanField(
                default=False,
                help_text='True if this is an anonymous/walk-in customer transaction'
            ),
        ),
    ]
