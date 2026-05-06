from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Project, ProjectMembership


@admin.register(ProjectMembership)
class ProjectMembershipAdmin(admin.ModelAdmin):
    list_display = ['id', 'project', 'user', 'role', 'joined_at']
    list_filter = ['role', 'project']
    raw_id_fields = ['project', 'user']
    search_fields = ['user__email', 'user__username', 'project__title']


class ProjectMembershipInline(admin.TabularInline):
    model = ProjectMembership
    extra = 0
    raw_id_fields = ['user']


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'owner', 'status', 'access_level',
        'start_date', 'end_date', 'labeling_datasets_count', 'members_count', 'created_at',
    ]
    list_filter = [
        'status', 'access_level', 'created_at', 'start_date', 'end_date',
    ]
    search_fields = [
        'title', 'description', 'abstract', 'keywords', 'tags',
        'owner__username', 'owner__email', 'funding_source', 'grant_number',
    ]
    list_editable = ['status', 'access_level']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [ProjectMembershipInline]
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'abstract'),
        }),
        ('Project Timeline', {
            'fields': ('start_date', 'end_date', 'status'),
        }),
        ('Access & Permissions', {
            'fields': ('access_level', 'owner'),
        }),
        ('Categorization', {
            'fields': ('keywords', 'tags'),
        }),
        ('External References', {
            'fields': ('project_url', 'funding_source', 'grant_number'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def labeling_datasets_count(self, obj):
        try:
            return obj.labeling_datasets.count()
        except Exception:
            return 0
    labeling_datasets_count.short_description = _('Label datasets')

    def members_count(self, obj):
        return obj.memberships.count()
    members_count.short_description = _('Members')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('owner').prefetch_related('memberships')
