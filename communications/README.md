# Communications App Installation Guide

## Overview
The `communications` app provides two-way messaging functionality between customers and businesses, marketing campaigns, notifications, and message templates.

## Features
- **Two-way Messaging**: Customers can send messages to businesses, and businesses can send messages to customers
- **Marketing Campaigns**: Create and send targeted marketing campaigns to customer segments
- **Notifications**: In-app notification system with read/unread tracking
- **Message Templates**: Reusable message templates with variable substitution
- **Auto-notifications**: Automatic notification creation when messages are sent

## Models
1. **Message** - Messages between customers and businesses
2. **MarketingCampaign** - Marketing campaigns with targeting and analytics
3. **Notification** - In-app notifications for customers
4. **MessageTemplate** - Reusable message templates

## Installation Instructions

### Step 1: Copy the communications folder
Copy the entire `communications` folder to your Django project directory:
```
C:\Users\Admin\OneDrive\Documents\Environment\ayende-cx\communications\
```

### Step 2: Add to INSTALLED_APPS
Edit `config/settings.py` and add 'communications' to INSTALLED_APPS:

```python
INSTALLED_APPS = [
    # ... other apps
    'billing',
    'communications',  # ADD THIS LINE
    # ... rest of apps
]
```

### Step 3: Create migrations
Run the following commands in PowerShell:

```powershell
cd C:\Users\Admin\OneDrive\Documents\Environment\ayende-cx

# Create migrations
python manage.py makemigrations communications

# Apply migrations
python manage.py migrate communications
```

### Step 4: Create superuser (if needed)
If you need to access the Django admin:
```powershell
python manage.py createsuperuser
```

### Step 5: Test locally
```powershell
python manage.py runserver
```

Visit http://127.0.0.1:8000/admin/ and verify you can see the Communications section.

### Step 6: Deploy to Railway

```powershell
# Add all files
git add .

# Commit changes
git commit -m "Add communications app with messaging and campaigns"

# Push to Railway
git push

# Run migrations on Railway
railway run python manage.py migrate
```

## Admin Interface
After installation, the Django admin will have these new sections:
- Messages
- Marketing Campaigns
- Notifications
- Message Templates

## Usage Examples

### Creating a message programmatically
```python
from communications.models import Message
from django.utils import timezone

message = Message.objects.create(
    tenant=tenant,
    receiver_customer=customer,
    message_type='business_to_customer',
    subject='Welcome!',
    body='Welcome to our store!',
    status='sent',
    sent_at=timezone.now()
)
```

### Sending a marketing campaign
```python
from communications.models import MarketingCampaign

campaign = MarketingCampaign.objects.create(
    tenant=tenant,
    name='Summer Sale 2025',
    subject='20% Off Everything',
    body='Get 20% off all items this summer!',
    target_audience='all',
    status='draft',
    created_by=staff_user
)

# Send the campaign
campaign.send_campaign()
```

### Creating a notification
```python
from communications.models import Notification

notification = Notification.objects.create(
    tenant=tenant,
    customer=customer,
    notification_type='reward',
    title='Reward Available!',
    message='You earned a $10 reward!',
    link_url='/rewards/'
)
```

## Testing
Run tests with:
```powershell
python manage.py test communications
```

## Next Steps
After installing the communications app:
1. Add customer dashboard views to `dashboard/views/main.py`
2. Create customer dashboard template
3. Create messaging interface templates
4. Add URL routes
5. Test the complete flow

## Troubleshooting

### Import errors
If you get import errors, make sure:
- The `communications` app is in the correct directory
- It's added to INSTALLED_APPS
- Migrations have been created and applied

### Foreign key errors
The communications app depends on:
- `tenants.Tenant` model
- `customers.TenantCustomer` model

Make sure these apps are installed and migrated first.

## File Structure
```
communications/
├── __init__.py
├── admin.py          # Django admin configuration
├── apps.py           # App configuration
├── models.py         # Database models
├── signals.py        # Signal handlers
├── tests.py          # Unit tests
├── views.py          # Views (placeholder)
├── migrations/
│   └── __init__.py
└── README.md         # This file
```

## Support
For issues or questions, refer to the main project documentation or session handover documents.
