from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.mail import send_mail
from django.conf import settings
import json
import logging

logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["POST"])
def contact_form_view(request):
    """
    Handle contact form submissions and send email to admin@ayendecx.com
    """
    try:
        # Parse JSON data
        data = json.loads(request.body)
        
        # Extract form fields
        first_name = data.get('firstName', '')
        last_name = data.get('lastName', '')
        email = data.get('email', '')
        phone = data.get('phone', '')
        company = data.get('company', '')
        service = data.get('service', '')
        message = data.get('message', '')
        
        # Validate required fields
        if not all([first_name, last_name, email, service, message]):
            return JsonResponse({
                'success': False,
                'error': 'Missing required fields'
            }, status=400)
        
        # Prepare email content
        subject = f'New Contact Form Submission: {service}'
        
        email_body = f"""
New Contact Form Submission from Ayende CX Website

CONTACT DETAILS:
----------------
Name: {first_name} {last_name}
Email: {email}
Phone: {phone if phone else 'Not provided'}
Company: {company if company else 'Not provided'}
Service Interest: {service}

MESSAGE:
--------
{message}

SUBMISSION TIME: {data.get('timestamp', 'Not provided')}

---
This email was automatically generated from the contact form at ayendecx.com
        """
        
        # Send email
        try:
            send_mail(
                subject=subject,
                message=email_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=['admin@ayendecx.com'],
                fail_silently=False,
            )
            
            logger.info(f'Contact form email sent successfully from {email}')
            
            return JsonResponse({
                'success': True,
                'message': 'Thank you for your message! We will get back to you within 24 hours.'
            })
            
        except Exception as email_error:
            logger.error(f'Error sending contact form email: {str(email_error)}')
            return JsonResponse({
                'success': False,
                'error': 'Failed to send email. Please try again or contact us directly.'
            }, status=500)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
        
    except Exception as e:
        logger.error(f'Error processing contact form: {str(e)}')
        return JsonResponse({
            'success': False,
            'error': 'An error occurred processing your request'
        }, status=500)