"""
AyendeCX Chatbot API Views
Powered by Anthropic's Claude API
"""
import json
import uuid
from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from investment.models import InvestmentLead, LeadActivity
import anthropic


# In-memory session storage (consider using Redis/database for production)
CHAT_SESSIONS = {}


def get_system_prompt(subdomain):
    """Get chatbot system prompt based on subdomain"""
    
    if subdomain == 'platform':
        return """You are Omoh, the friendly AI assistant for AyendeCX - a cutting-edge multi-currency POS and CRM platform designed specifically for African businesses and diaspora entrepreneurs.

Your role is to:
1. Welcome visitors warmly and professionally
2. Answer questions about AyendeCX's products and services
3. Qualify investment leads by gathering key information
4. Provide information about the platform's features
5. Guide interested parties toward next steps

Key Platform Features:
- Multi-tenant POS system with offline-first capability
- Integrated CRM for customer relationship management  
- Multi-currency support for African markets
- Real-time customer insights and analytics
- Loyalty rewards and redemption tracking
- Automated business workflows
- SMS and email marketing campaigns

Target Market:
- African businesses (retail, rental, service, hospitality)
- Diaspora entrepreneurs
- Multi-location businesses needing centralized control

Investment Opportunity:
- Pre-seed funding phase
- SAFE investment structure
- $4.2B market opportunity
- Addressing fragmented customer data problem

When chatting:
- Be conversational and friendly
- Keep responses concise (2-3 sentences usually)
- Ask one question at a time
- For investment inquiries, gather: name, email, investment interest level
- Offer to connect them with the founding team for detailed discussions

IMPORTANT: Do not make up information. If you don't know something, say so and offer to connect them with the team."""
    
    return "You are a helpful AI assistant."


@csrf_exempt
@require_http_methods(["POST"])
def initialize_session(request, subdomain):
    """Initialize a new chat session"""
    try:
        data = json.loads(request.body)
        visitor_info = data.get('visitor_info', {})
        
        # Create session
        session_id = str(uuid.uuid4())
        CHAT_SESSIONS[session_id] = {
            'subdomain': subdomain,
            'visitor_info': visitor_info,
            'messages': [],
            'created_at': datetime.now().isoformat(),
            'lead_id': None
        }
        
        # Welcome message
        if subdomain == 'platform':
            welcome = "Hi! I'm Omoh, your AyendeCX assistant. How can I help you today?"
        else:
            welcome = f"Hello! Welcome to {subdomain}. How can I assist you?"
        
        return JsonResponse({
            'success': True,
            'session_id': session_id,
            'welcome_message': welcome
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def send_message(request, subdomain):
    """Send a message and get AI response"""
    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')
        message = data.get('message', '').strip()
        visitor_info = data.get('visitor_info', {})
        
        if not session_id or session_id not in CHAT_SESSIONS:
            return JsonResponse({
                'success': False,
                'error': 'Invalid session'
            }, status=400)
        
        if not message:
            return JsonResponse({
                'success': False,
                'error': 'Message is required'
            }, status=400)
        
        session = CHAT_SESSIONS[session_id]
        
        # Add user message to session
        session['messages'].append({
            'role': 'user',
            'content': message,
            'timestamp': datetime.now().isoformat()
        })
        
        # Get AI response
        response_text = get_ai_response(session, message, subdomain)
        
        # Add bot response to session
        session['messages'].append({
            'role': 'assistant',
            'content': response_text,
            'timestamp': datetime.now().isoformat()
        })
        
        # Check if this is an investment lead
        if subdomain == 'platform':
            detect_and_create_lead(session, message, visitor_info)
        
        return JsonResponse({
            'success': True,
            'message': response_text
        })
        
    except Exception as e:
        print(f"Chatbot error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to process message'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def close_session(request, subdomain):
    """Close a chat session"""
    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')
        
        if session_id and session_id in CHAT_SESSIONS:
            # Optionally save session to database here
            del CHAT_SESSIONS[session_id]
        
        return JsonResponse({
            'success': True
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


def get_ai_response(session, message, subdomain):
    """Get response from Anthropic Claude API"""
    
    # Check if API key is configured
    api_key = settings.ANTHROPIC_API_KEY
    if not api_key:
        return "I'm currently unavailable. Please try again later or contact our team directly."
    
    try:
        client = anthropic.Anthropic(api_key=api_key)
        
        # Build conversation history for Claude
        conversation_messages = []
        for msg in session['messages']:
            conversation_messages.append({
                'role': msg['role'],
                'content': msg['content']
            })
        
        # Get system prompt
        system_prompt = get_system_prompt(subdomain)
        
        # Call Claude API
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system=system_prompt,
            messages=conversation_messages
        )
        
        # Extract text from response
        return response.content[0].text
        
    except Exception as e:
        print(f"Anthropic API error: {str(e)}")
        return "I'm having trouble connecting right now. Please try again in a moment."


def detect_and_create_lead(session, message, visitor_info):
    """Detect investment interest and create lead"""
    
    # Skip if lead already created for this session
    if session.get('lead_id'):
        return
    
    # Simple keyword detection
    investment_keywords = [
        'invest', 'investment', 'funding', 'raise', 'capital',
        'investor', 'interested', 'opportunity', 'seed'
    ]
    
    message_lower = message.lower()
    has_investment_interest = any(keyword in message_lower for keyword in investment_keywords)
    
    if not has_investment_interest:
        return
    
    try:
        # Create lead
        lead = InvestmentLead.objects.create(
            source='chatbot',
            status='new',
            score=50,  # Medium score for chatbot leads
            metadata={
                'session_id': session.get('created_at', ''),
                'first_message': session['messages'][0]['content'] if session['messages'] else '',
                'trigger_message': message
            }
        )
        
        # Create activity
        LeadActivity.objects.create(
            lead=lead,
            activity_type='chatbot_conversation',
            description=f"Started conversation via chatbot. Expressed interest in: {message[:100]}"
        )
        
        session['lead_id'] = lead.id
        
    except Exception as e:
        print(f"Error creating lead from chatbot: {str(e)}")
