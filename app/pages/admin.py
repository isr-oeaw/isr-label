from django.contrib import admin
from django.contrib.sites.models import Site
from django.utils.html import format_html
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from .models import Announcement

# Unregister the Site model from admin
admin.site.unregister(Site)


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    """
    Admin interface for Announcement model
    """
    
    list_display = [
        'title', 
        'priority', 
        'is_active', 
        'is_currently_valid', 
        'created_by', 
        'created_at',
        'valid_from',
        'valid_until'
    ]
    
    list_filter = [
        'priority',
        'is_active',
        'created_at',
        'valid_from',
        'valid_until',
        'created_by'
    ]
    
    search_fields = [
        'title',
        'message',
        'created_by__username',
        'created_by__email'
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
        'is_currently_valid',
        'is_displayed'
    ]
    
    fieldsets = (
        (_('Content'), {
            'fields': ('title', 'message', 'priority')
        }),
        (_('Status'), {
            'fields': ('is_active', 'is_currently_valid', 'is_displayed')
        }),
        (_('Scheduling'), {
            'fields': ('valid_from', 'valid_until'),
            'description': _('Set when the announcement should be displayed. Leave "Valid Until" empty for no end date.')
        }),
        (_('Metadata'), {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Automatically set created_by to current user if not set"""
        if not change:  # Only for new objects
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def is_currently_valid(self, obj):
        """Display current validity status with color coding"""
        if obj.is_currently_valid:
            return format_html(
                '<span style="color: green;">✓ {}</span>',
                _('Valid')
            )
        else:
            return format_html(
                '<span style="color: red;">✗ {}</span>',
                _('Invalid')
            )
    is_currently_valid.short_description = _('Currently Valid')
    is_currently_valid.boolean = True
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('created_by')