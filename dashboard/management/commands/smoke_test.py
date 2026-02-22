"""
Smoke Test Management Command
Tests critical URLs to verify deployment success

Usage:
    python manage.py smoke_test
    python manage.py smoke_test --json
    python manage.py smoke_test --admin-only
    python manage.py smoke_test --quick

Location: dashboard/management/commands/smoke_test.py
"""

from django.core.management.base import BaseCommand
from django.test import Client
from django.contrib.auth import get_user_model
import json
import sys


class Command(BaseCommand):
    help = 'Run smoke tests on critical URLs to verify deployment'

    def add_arguments(self, parser):
        parser.add_argument(
            '--json',
            action='store_true',
            help='Output results in JSON format',
        )
        parser.add_argument(
            '--admin-only',
            action='store_true',
            help='Only test admin pages',
        )
        parser.add_argument(
            '--quick',
            action='store_true',
            help='Run quick tests (fewer URLs)',
        )

    def handle(self, *args, **options):
        """Run smoke tests"""
        client = Client()
        results = []
        
        # Get or create test admin user
        User = get_user_model()
        try:
            admin_user = User.objects.filter(is_superuser=True).first()
            if not admin_user:
                self.stdout.write(self.style.ERROR('No superuser found. Cannot test admin pages.'))
                return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error getting admin user: {e}'))
            return

        # Login as admin for admin page tests
        client.force_login(admin_user)

        # Define test URLs
        admin_urls = [
            '/admin/',
            '/admin/tenants/tenant/',
            '/admin/tenants/tenantsettings/',
            '/admin/customers/customer/',
            '/admin/customers/tenantcustomer/',
            '/admin/customers/transaction/',
            '/admin/rewards/reward/',
            '/admin/rewards/redemption/',
            '/admin/billing/platformpayment/',
            '/admin/billing/subscriptionplan/',
            '/admin/investment/investmentlead/',
            '/admin/investment/leadactivity/',
            '/admin/investment/leadnote/',
            '/admin/provisioning/provisioningtoken/',
            '/admin/provisioning/setupwizardprogress/',
            '/admin/notifications/notification/',
        ]

        frontend_urls = [
            '/',
            '/health/',
        ]

        # Select URLs based on options
        if options['admin_only']:
            urls_to_test = admin_urls
        elif options['quick']:
            urls_to_test = [
                '/admin/',
                '/admin/tenants/tenant/',
                '/admin/customers/customer/',
                '/',
                '/health/',
            ]
        else:
            urls_to_test = admin_urls + frontend_urls

        # Run tests
        if not options['json']:
            self.stdout.write(self.style.WARNING(f'\n🔍 Running smoke tests on {len(urls_to_test)} URLs...\n'))

        passed = 0
        failed = 0

        for url in urls_to_test:
            try:
                response = client.get(url, follow=False)
                status = response.status_code
                
                # Consider 200, 302 (redirect) as success
                # 500, 404 as failure
                if status in [200, 302]:
                    passed += 1
                    result = {
                        'url': url,
                        'status': status,
                        'passed': True,
                        'error': None
                    }
                    if not options['json']:
                        self.stdout.write(
                            self.style.SUCCESS(f'✓ {url} [{status}]')
                        )
                else:
                    failed += 1
                    result = {
                        'url': url,
                        'status': status,
                        'passed': False,
                        'error': f'Unexpected status code: {status}'
                    }
                    if not options['json']:
                        self.stdout.write(
                            self.style.ERROR(f'✗ {url} [{status}]')
                        )
                
                results.append(result)
                
            except Exception as e:
                failed += 1
                result = {
                    'url': url,
                    'status': None,
                    'passed': False,
                    'error': str(e)
                }
                results.append(result)
                if not options['json']:
                    self.stdout.write(
                        self.style.ERROR(f'✗ {url} [ERROR: {str(e)}]')
                    )

        # Output results
        if options['json']:
            output = {
                'total': len(urls_to_test),
                'passed': passed,
                'failed': failed,
                'success_rate': round((passed / len(urls_to_test)) * 100, 2) if urls_to_test else 0,
                'results': results
            }
            self.stdout.write(json.dumps(output, indent=2))
        else:
            self.stdout.write('\n' + '='*60)
            self.stdout.write(
                self.style.WARNING(
                    f'\n📊 Results: {passed}/{len(urls_to_test)} tests passed '
                    f'({round((passed/len(urls_to_test))*100, 1)}%)\n'
                )
            )
            
            if failed == 0:
                self.stdout.write(self.style.SUCCESS('✅ All smoke tests passed!\n'))
            else:
                self.stdout.write(self.style.ERROR(f'❌ {failed} tests failed!\n'))

        # Exit with appropriate code for CI/CD
        if failed > 0:
            sys.exit(1)
        else:
            sys.exit(0)
