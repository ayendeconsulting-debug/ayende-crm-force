"""
Tests for Communications App
"""

from django.test import TestCase
from django.utils import timezone
from customers.models import TenantCustomer
from tenants.models import Tenant
from .models import Message, MarketingCampaign, Notification, MessageTemplate


class MessageModelTests(TestCase):
    """Test cases for Message model"""
    
    def setUp(self):
        """Set up test data"""
        self.tenant = Tenant.objects.create(
            name="Test Business",
            subdomain="testbiz"
        )
        self.customer = TenantCustomer.objects.create(
            tenant=self.tenant,
            email="customer@test.com",
            username="customer.testbiz",
            first_name="John",
            last_name="Doe",
            role="customer"
        )
    
    def test_message_creation(self):
        """Test creating a message"""
        message = Message.objects.create(
            tenant=self.tenant,
            receiver_customer=self.customer,
            message_type='business_to_customer',
            subject='Test Message',
            body='This is a test message',
            status='sent',
            sent_at=timezone.now()
        )
        self.assertEqual(message.subject, 'Test Message')
        self.assertTrue(message.is_unread)
    
    def test_mark_as_read(self):
        """Test marking message as read"""
        message = Message.objects.create(
            tenant=self.tenant,
            receiver_customer=self.customer,
            message_type='business_to_customer',
            subject='Test',
            body='Test',
            status='sent'
        )
        message.mark_as_read()
        self.assertEqual(message.status, 'read')
        self.assertIsNotNone(message.read_at)


class MarketingCampaignTests(TestCase):
    """Test cases for Marketing Campaign"""
    
    def setUp(self):
        """Set up test data"""
        self.tenant = Tenant.objects.create(
            name="Test Business",
            subdomain="testbiz"
        )
    
    def test_campaign_creation(self):
        """Test creating a campaign"""
        campaign = MarketingCampaign.objects.create(
            tenant=self.tenant,
            name='Summer Sale',
            subject='20% Off Everything',
            body='Get 20% off all items this summer!',
            target_audience='all',
            status='draft'
        )
        self.assertEqual(campaign.name, 'Summer Sale')
        self.assertEqual(campaign.status, 'draft')


class NotificationTests(TestCase):
    """Test cases for Notifications"""
    
    def setUp(self):
        """Set up test data"""
        self.tenant = Tenant.objects.create(
            name="Test Business",
            subdomain="testbiz"
        )
        self.customer = TenantCustomer.objects.create(
            tenant=self.tenant,
            email="customer@test.com",
            username="customer.testbiz",
            first_name="John",
            last_name="Doe",
            role="customer"
        )
    
    def test_notification_creation(self):
        """Test creating a notification"""
        notification = Notification.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            notification_type='message',
            title='New Message',
            message='You have a new message'
        )
        self.assertEqual(notification.title, 'New Message')
        self.assertFalse(notification.is_read)
    
    def test_mark_notification_as_read(self):
        """Test marking notification as read"""
        notification = Notification.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            notification_type='message',
            title='Test',
            message='Test'
        )
        notification.mark_as_read()
        self.assertTrue(notification.is_read)
        self.assertIsNotNone(notification.read_at)
