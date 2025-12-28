from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone


def send_lead_notification_email(lead):
    """
    Send email notification to admin@ayendecx.com when new lead is created
    """
    priority_emoji = {
        'hot': '🔥',
        'warm': '⚡',
        'cold': '❄️'
    }
    
    subject = f"{priority_emoji.get(lead.priority, '')} New Investment Lead - {lead.full_name} - ${lead.investment_amount}"
    
    # Plain text email
    message = f"""
New Investment Lead Received

PRIORITY: {lead.priority.upper()}
LEAD SCORE: {lead.lead_score}/100

CONTACT INFORMATION:
Name: {lead.full_name}
Email: {lead.email}
Phone: {lead.phone_number if lead.phone_number else 'Not provided'}
Company: {lead.company_name if lead.company_name else 'Not provided'}
LinkedIn: {lead.linkedin_profile if lead.linkedin_profile else 'Not provided'}

INVESTMENT DETAILS:
Amount: ${lead.investment_amount}
Accredited Investor: {'Yes' if lead.accredited_investor else 'No'}

TRACKING:
Submitted: {lead.created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC
Source: {lead.get_source_display()}
IP Address: {lead.ip_address if lead.ip_address else 'Not captured'}
Assigned To: {lead.assigned_to.get_full_name() if lead.assigned_to else 'Unassigned'}
Next Follow-up: {lead.next_follow_up_date.strftime('%Y-%m-%d') if lead.next_follow_up_date else 'Not set'}

View Lead Details: https://ayendecx.com/investment/leads/{lead.id}/

---
AyendeCX Investment Platform
Automated Notification - Do Not Reply
    """
    
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = ['admin@ayendecx.com']
    reply_to = ['admin@ayendecx.com'] 
    
    try:
        send_mail(
            subject,
            message,
            from_email,
            recipient_list,
            fail_silently=False,
            reply_to=reply_to,
        )
    except Exception as e:
        print(f"Error sending lead notification email: {e}")


def send_investor_welcome_email(lead):
    """
    Send welcome/thank you email to investor after form submission
    """
    subject = "Thank You for Your Interest in AyendeCX"
    
    message = f"""
Dear {lead.full_name},

Thank you for expressing interest in AyendeCX's investment opportunity.

We've received your information and our team will review it shortly. You can expect to hear from us within 24 hours to discuss the next steps.

In the meantime, feel free to:

📅 Schedule a call with our founder: https://calendly.com/ayendeconsulting/30min
📧 Email us directly: admin@ayendecx.com
🌐 Learn more about AyendeCX: https://ayendecx.com

INVESTMENT DETAILS RECEIVED:
Investment Amount: ${lead.investment_amount}
Accredited Investor: {'Yes' if lead.accredited_investor else 'No'}

We're excited about the opportunity to have you join us on this journey to transform African commerce.

Best regards,

Adesanya Ehinmidu
Founder & CEO
AyendeCX Inc.
Toronto, Ontario, Canada

---
This is an automated message. Please do not reply directly to this email.
For inquiries, contact us at admin@ayendecx.com
    """
    
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [lead.email]
    reply_to = ['admin@ayendecx.com'] 
    
    try:
        send_mail(
            subject,
            message,
            from_email,
            recipient_list,
            fail_silently=False,
            reply_to=reply_to,
        )
    except Exception as e:
        print(f"Error sending investor welcome email: {e}")


def get_client_ip(request):
    """
    Get client IP address from request
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
