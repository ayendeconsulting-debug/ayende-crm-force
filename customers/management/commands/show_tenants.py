"""
Django management command to display tenant information (UUID and subdomain).
This is used to sync tenant UUIDs between CRM and POS systems.

Usage:
    python manage.py show_tenants
    
    or via Railway:
    railway run python manage.py show_tenants
"""

from django.core.management.base import BaseCommand
from tenants.models import Tenant


class Command(BaseCommand):
    help = 'Display all tenants with their UUIDs and subdomains for POS sync'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n=== TENANT INFORMATION FOR POS SYNC ===\n'))
        
        tenants = Tenant.objects.all().order_by('subdomain')
        
        if not tenants.exists():
            self.stdout.write(self.style.WARNING('No tenants found in database.'))
            return
        
        # Display header
        self.stdout.write(self.style.HTTP_INFO(f"{'Subdomain':<20} {'UUID':<40} {'Name':<30}"))
        self.stdout.write(self.style.HTTP_INFO('-' * 90))
        
        # Display each tenant
        for tenant in tenants:
            self.stdout.write(
                f"{tenant.subdomain:<20} {str(tenant.id):<40} {tenant.name:<30}"
            )
        
        self.stdout.write(self.style.SUCCESS(f'\nTotal tenants: {tenants.count()}'))
        
        # Provide update instructions
        self.stdout.write(self.style.WARNING('\n=== POS DATABASE UPDATE INSTRUCTIONS ===\n'))
        self.stdout.write('Update the POS Business table with these UUIDs:\n')
        
        for tenant in tenants:
            self.stdout.write(
                f"UPDATE Business SET externalTenantId = '{tenant.id}' "
                f"WHERE businessName = '{tenant.name}';\n"
            )
        
        self.stdout.write(self.style.SUCCESS('\n=== END ===\n'))
