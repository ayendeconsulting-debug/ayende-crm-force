from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import InvestmentLead, LeadActivity, LeadNote
from .forms import InvestmentLeadForm, LeadNoteForm, LeadActivityForm
from .utils import get_client_ip


def landing_page(request):
    """
    Public investment infographic landing page
    """
    if request.method == 'POST':
        form = InvestmentLeadForm(request.POST)
        if form.is_valid():
            # Create lead instance but don't save yet
            lead = form.save(commit=False)
            
            # Add tracking information
            lead.ip_address = get_client_ip(request)
            lead.user_agent = request.META.get('HTTP_USER_AGENT', '')
            lead.source = 'website'
            
            # Capture UTM parameters if present
            lead.utm_source = request.GET.get('utm_source', '')
            lead.utm_campaign = request.GET.get('utm_campaign', '')
            lead.utm_medium = request.GET.get('utm_medium', '')
            
            # Save the lead (signals will handle auto-assignment and emails)
            lead.save()
            
            # Return success response
            return JsonResponse({
                'success': True,
                'message': 'Thank you for your interest! Check your email for next steps.'
            })
        else:
            # Return form errors
            return JsonResponse({
                'success': False,
                'errors': form.errors
            }, status=400)
    
    # GET request - show the landing page
    form = InvestmentLeadForm()
    context = {
        'form': form,
    }
    return render(request, 'investment/landing.html', context)


@login_required
def lead_list(request):
    """
    List all investment leads (admin and sales team only)
    """
    # Check if user has permission to view leads
    if not (request.user.is_superuser or 
            request.user.groups.filter(name__in=['Investment Admin', 'Investment Sales']).exists()):
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('/')
    
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    priority_filter = request.GET.get('priority', '')
    assigned_filter = request.GET.get('assigned', '')
    
    # Base queryset
    leads = InvestmentLead.objects.all()
    
    # Apply filters
    if status_filter:
        leads = leads.filter(status=status_filter)
    if priority_filter:
        leads = leads.filter(priority=priority_filter)
    if assigned_filter:
        if assigned_filter == 'me':
            leads = leads.filter(assigned_to=request.user)
        elif assigned_filter == 'unassigned':
            leads = leads.filter(assigned_to__isnull=True)
    
    # If user is sales (not admin), only show their assigned leads
    if not request.user.is_superuser and not request.user.groups.filter(name='Investment Admin').exists():
        leads = leads.filter(assigned_to=request.user)
    
    # Order by priority and score
    leads = leads.order_by('-priority', '-lead_score', '-created_at')
    
    context = {
        'leads': leads,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'assigned_filter': assigned_filter,
    }
    return render(request, 'investment/lead_list.html', context)


@login_required
def lead_detail(request, lead_id):
    """
    View detailed information about a specific lead
    """
    lead = get_object_or_404(InvestmentLead, id=lead_id)
    
    # Check permission
    if not (request.user.is_superuser or 
            request.user.groups.filter(name__in=['Investment Admin', 'Investment Sales']).exists() or
            lead.assigned_to == request.user):
        messages.error(request, 'You do not have permission to view this lead.')
        return redirect('/investment/leads/')
    
    # Get all activities and notes
    activities = lead.activities.all()[:20]  # Last 20 activities
    notes = lead.notes.all()
    
    context = {
        'lead': lead,
        'activities': activities,
        'notes': notes,
        'note_form': LeadNoteForm(),
        'activity_form': LeadActivityForm(),
    }
    return render(request, 'investment/lead_detail.html', context)


@login_required
def add_note(request, lead_id):
    """
    Add a note to a lead
    """
    lead = get_object_or_404(InvestmentLead, id=lead_id)
    
    if request.method == 'POST':
        form = LeadNoteForm(request.POST)
        if form.is_valid():
            note = form.save(commit=False)
            note.lead = lead
            note.created_by = request.user
            note.save()
            
            # Log activity
            LeadActivity.objects.create(
                lead=lead,
                activity_type='note',
                subject='Note Added',
                description=note.note[:100],
                performed_by=request.user
            )
            
            messages.success(request, 'Note added successfully.')
        else:
            messages.error(request, 'Error adding note.')
    
    return redirect('investment:lead_detail', lead_id=lead_id)


@login_required
def add_activity(request, lead_id):
    """
    Add an activity to a lead
    """
    lead = get_object_or_404(InvestmentLead, id=lead_id)
    
    if request.method == 'POST':
        form = LeadActivityForm(request.POST)
        if form.is_valid():
            activity = form.save(commit=False)
            activity.lead = lead
            activity.performed_by = request.user
            activity.save()
            
            messages.success(request, 'Activity logged successfully.')
        else:
            messages.error(request, 'Error logging activity.')
    
    return redirect('investment:lead_detail', lead_id=lead_id)
