from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import InvestmentLead, LeadActivity, LeadNote


class LeadActivityInline(admin.TabularInline):
    model = LeadActivity
    extra = 0
    readonly_fields = ['performed_at', 'performed_by']
    fields = ['activity_type', 'subject', 'description', 'outcome', 'performed_at', 'performed_by']
    
    def has_delete_permission(self, request, obj=None):
        return False


class LeadNoteInline(admin.TabularInline):
    model = LeadNote
    extra = 0
    readonly_fields = ['created_at', 'created_by']
    fields = ['note', 'is_pinned', 'created_at', 'created_by']


@admin.register(InvestmentLead)
class InvestmentLeadAdmin(ModelAdmin):
    list_display = [
        'full_name',
        'email',
        'investment_amount',
        'priority_badge',
        'status_badge',
        'lead_score',
        'assigned_to',
        'created_at',
        'next_follow_up_date'
    ]
    
    list_filter = [
        'status',
        'priority',
        'accredited_investor',
        'source',
        'created_at',
        'assigned_to'
    ]
    
    search_fields = [
        'full_name',
        'email',
        'company_name',
        'phone_number'
    ]
    
    readonly_fields = [
        'id',
        'lead_score',
        'priority',
        'created_at',
        'updated_at',
        'converted_at',
        'ip_address',
        'user_agent'
    ]
    
    fieldsets = (
        ('Contact Information', {
            'fields': ('full_name', 'email', 'phone_number', 'company_name', 'linkedin_profile')
        }),
        ('Investment Details', {
            'fields': ('investment_amount', 'accredited_investor')
        }),
        ('Lead Management', {
            'fields': ('status', 'lead_score', 'priority', 'assigned_to', 'next_follow_up_date', 'follow_up_count')
        }),
        ('Tracking', {
            'fields': ('source', 'referral_source', 'utm_source', 'utm_campaign', 'utm_medium', 'ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
        ('Conversion', {
            'fields': ('converted_at', 'conversion_amount', 'lost_reason'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('id', 'created_at', 'updated_at', 'last_contacted_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [LeadNoteInline, LeadActivityInline]
    
    actions = ['mark_as_contacted', 'mark_as_qualified', 'assign_to_me']
    
    def priority_badge(self, obj):
        colors = {
            'hot': '🔥 Hot',
            'warm': '⚡ Warm',
            'cold': '❄️ Cold'
        }
        return colors.get(obj.priority, obj.priority)
    priority_badge.short_description = 'Priority'
    
    def status_badge(self, obj):
        return obj.get_status_display()
    status_badge.short_description = 'Status'
    
    def mark_as_contacted(self, request, queryset):
        updated = queryset.update(status='contacted')
        self.message_user(request, f'{updated} leads marked as contacted.')
    mark_as_contacted.short_description = 'Mark selected as Contacted'
    
    def mark_as_qualified(self, request, queryset):
        updated = queryset.update(status='qualified')
        self.message_user(request, f'{updated} leads marked as qualified.')
    mark_as_qualified.short_description = 'Mark selected as Qualified'
    
    def assign_to_me(self, request, queryset):
        updated = queryset.update(assigned_to=request.user)
        self.message_user(request, f'{updated} leads assigned to you.')
    assign_to_me.short_description = 'Assign selected to me'


@admin.register(LeadActivity)
class LeadActivityAdmin(ModelAdmin):
    list_display = [
        'lead',
        'activity_type',
        'subject',
        'outcome',
        'performed_by',
        'performed_at'
    ]
    
    list_filter = [
        'activity_type',
        'outcome',
        'performed_at',
        'performed_by'
    ]
    
    search_fields = [
        'lead__full_name',
        'lead__email',
        'subject',
        'description'
    ]
    
    readonly_fields = ['id', 'performed_at']
    
    date_hierarchy = 'performed_at'


@admin.register(LeadNote)
class LeadNoteAdmin(ModelAdmin):
    list_display = [
        'lead',
        'note_preview',
        'is_pinned',
        'created_by',
        'created_at'
    ]
    
    list_filter = [
        'is_pinned',
        'created_at',
        'created_by'
    ]
    
    search_fields = [
        'lead__full_name',
        'lead__email',
        'note'
    ]
    
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    def note_preview(self, obj):
        return obj.note[:100] + '...' if len(obj.note) > 100 else obj.note
    note_preview.short_description = 'Note'
