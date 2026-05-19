from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from auditlog.registry import auditlog
from auditlog.models import AuditlogHistoryField


class Role(models.Model):
    """Role model for role-based access control"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    permissions = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_permissions(self):
        """Get list of permissions for this role"""
        if isinstance(self.permissions, list):
            return self.permissions
        elif isinstance(self.permissions, dict):
            return self.permissions.get('permissions', [])
        return []

    def has_permission(self, permission):
        """Check if role has specific permission"""
        return permission in self.get_permissions()


class CustomUser(AbstractUser):
    history = AuditlogHistoryField()
    
    # Add role field
    role = models.ForeignKey(
        Role, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='users'
    )
    
    # Language preference
    language = models.CharField(
        max_length=10,
        choices=[
            ('en', _('English')),
            ('de', _('German')),
        ],
        default='en',
        verbose_name=_('Language'),
        help_text=_('Preferred language for the interface')
    )
    
    # Notification preferences
    email_notifications = models.BooleanField(
        default=False,
        verbose_name=_('Email Notifications'),
        help_text=_('Receive email notifications for comments on your datasets')
    )
    
    # Dataset notification preferences
    notify_dataset_updates = models.BooleanField(
        default=False,
        verbose_name=_('Dataset Updates'),
        help_text=_('Receive email notifications when datasets you follow are updated')
    )
    
    notify_new_versions = models.BooleanField(
        default=False,
        verbose_name=_('New Versions'),
        help_text=_('Receive email notifications when new versions of datasets you follow are published')
    )
    
    notify_comments = models.BooleanField(
        default=False,
        verbose_name=_('Comments'),
        help_text=_('Receive email notifications for comments on your datasets')
    )
    
    # User approval system
    is_approved = models.BooleanField(
        default=False,
        verbose_name=_('Approved'),
        help_text=_('Whether this user has been approved by an administrator')
    )
    
    # First login tracking for help section
    first_login_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('First Login Date'),
        help_text=_('Date of the user\'s first login')
    )
    
    # Add related_name to avoid field clashes
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name='custom_user_set',
        related_query_name='custom_user',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name='custom_user_set',
        related_query_name='custom_user',
    )

    class Meta:
        ordering = ['username']

    def __str__(self):
        return f"{self.username} ({self.email})"

    def has_role_permission(self, permission):
        """Check if user has permission through their role"""
        if self.role and self.role.is_active:
            return self.role.has_permission(permission)
        return False

    def get_all_permissions(self):
        """Get all permissions for the user (Django + role-based)"""
        permissions = set()
        
        # Django permissions
        permissions.update(self.get_group_permissions())
        permissions.update(self.get_user_permissions())
        
        # Role-based permissions
        if self.role and self.role.is_active:
            permissions.update(self.role.get_permissions())
        
        return permissions

    def has_any_permission(self, permissions):
        """Check if user has any of the given permissions"""
        user_permissions = self.get_all_permissions()
        return any(perm in user_permissions for perm in permissions)

    def is_group_admin_of(self, group):
        """Check if user is a group admin of a specific group"""
        return group.has_group_admin(self)

    def get_group_admin_groups(self):
        """Get all groups where the user is a group admin"""
        from group.models import Group
        return Group.objects.filter(
            members__user=self,
            members__role='admin',
            members__is_active=True
        )

    def is_group_admin_anywhere(self):
        """Check if user is a group admin of any group"""
        return self.get_group_admin_groups().exists()

    def is_email_verified(self):
        """Check if the user's email is verified"""
        try:
            from allauth.account.models import EmailAddress
            email_address = EmailAddress.objects.get(user=self, email=self.email)
            return email_address.verified
        except (ImportError, EmailAddress.DoesNotExist):
            # If allauth is not available or no EmailAddress record exists,
            # assume email is verified (for backwards compatibility)
            return True


# Register models for audit logging
auditlog.register(CustomUser)
auditlog.register(Role)