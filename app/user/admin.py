# Admin registration is now handled in apps.py ready() method

from django.contrib import admin
from .models import Role, CustomUser


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at', 'updated_at', 'user_count']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Permissions', {
            'fields': ('permissions',),
            'description': 'Enter permissions as JSON. Example: {"permissions": ["user.view", "user.edit", "user.delete"]}'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def user_count(self, obj):
        return obj.users.count()
    user_count.short_description = 'Users with this role'


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'role', 'is_active', 'is_staff', 'date_joined']
    list_filter = ['is_active', 'is_staff', 'is_superuser', 'role', 'date_joined']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    readonly_fields = ['date_joined', 'last_login']
    
    fieldsets = (
        ('Personal Information', {
            'fields': ('username', 'email', 'first_name', 'last_name')
        }),
        ('Role & Permissions', {
            'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Important Dates', {
            'fields': ('date_joined', 'last_login'),
            'classes': ('collapse',)
        }),
    )
