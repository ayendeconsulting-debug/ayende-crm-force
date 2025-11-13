"""
Management command to send birthday messages.
Run daily via cron or Railway scheduler:

python manage.py send_birthday_messages
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date

from customers.models import TenantCustomer
from notifications.models import Message, MessageTemplate


class Command(BaseCommand):
    help = 'Send birthday greetings to customers whose birthday is today'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be sent without actually sending',
        )
        parser.add_argument(
            '--bonus-points',
            type=int,
            default=50,
            help='Bonus points to award (default: 50)',
        )
    
    def handle(self, *args, **options):
        today = date.today()
        dry_run = options['dry_run']
        bonus_points = options['bonus_points']
        
        self.stdout.write(f"🎂 Checking for birthdays on {today}...")
        
        # Find customers with birthday today
        customers = TenantCustomer.objects.filter(
            role='customer',
            is_active=True,
            date_of_birth__month=today.month,
            date_of_birth__day=today.day
        ).select_related('tenant')
        
        total_customers = customers.count()
        self.stdout.write(f"Found {total_customers} customers with birthdays today")
        
        if total_customers == 0:
            self.stdout.write(self.style.SUCCESS("No birthdays today!"))
            return
        
        messages_sent = 0
        
        for customer in customers:
            # Check if already sent this year
            already_sent = Message.objects.filter(
                tenant=customer.tenant,
                receiver=customer,
                template_used__template_type='birthday',
                sent_at__year=today.year
            ).exists()
            
            if already_sent:
                self.stdout.write(
                    self.style.WARNING(
                        f"  ⏭️  Skipping {customer.email} - already sent this year"
                    )
                )
                continue
            
            # Get or create birthday template
            template, _ = MessageTemplate.objects.get_or_create(
                tenant=customer.tenant,
                template_type='birthday',
                defaults={
                    'name': 'Birthday Greeting',
                    'subject': 'Happy Birthday {{first_name}}!',
                    'body': f'''Happy Birthday {{{{first_name}}}}!

{{{{business_name}}}} wishes you a wonderful birthday!

As a special gift, we're adding {bonus_points} bonus points to your account.

Hope to see you soon!

{{{{business_name}}}}''',
                    'created_by': None
                }
            )
            
            # Render template
            subject, body = template.render(customer)
            
            if dry_run:
                self.stdout.write(f"\n📧 Would send to: {customer.email}")
                self.stdout.write(f"   Subject: {subject}")
                self.stdout.write(f"   Points: +{bonus_points}")
            else:
                # Create and send message
                Message.objects.create(
                    tenant=customer.tenant,
                    sender=None,
                    receiver=customer,
                    message_type='business_to_customer',
                    subject=subject,
                    body=body,
                    priority='normal',
                    status='sent',
                    sent_at=timezone.now(),
                    template_used=template
                )
                
                # Award birthday points
                customer.loyalty_points += bonus_points
                customer.save()
                
                template.increment_usage()
                messages_sent += 1
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✅ Sent to {customer.email} (+{bonus_points} points)"
                    )
                )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"\n🔍 DRY RUN: Would have sent {total_customers} messages")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"\n✅ Successfully sent {messages_sent} birthday messages!")
            )