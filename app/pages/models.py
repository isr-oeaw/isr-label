from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

User = get_user_model()


class Announcement(models.Model):
    """
    Model for administrator announcements displayed on the dashboard
    """
    
    PRIORITY_CHOICES = [
        ('low', _('Low')),
        ('normal', _('Normal')),
        ('high', _('High')),
        ('urgent', _('Urgent')),
    ]
    
    title = models.CharField(
        max_length=200,
        verbose_name=_('Title'),
        help_text=_('Title of the announcement')
    )
    
    message = models.TextField(
        verbose_name=_('Message'),
        help_text=_('Content of the announcement')
    )
    
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='normal',
        verbose_name=_('Priority'),
        help_text=_('Priority level of the announcement')
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Active'),
        help_text=_('Whether this announcement is currently displayed')
    )
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_announcements',
        verbose_name=_('Created By'),
        help_text=_('Administrator who created this announcement')
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At'),
        help_text=_('When this announcement was created')
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated At'),
        help_text=_('When this announcement was last updated')
    )
    
    valid_from = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('Valid From'),
        help_text=_('When this announcement should start being displayed')
    )
    
    valid_until = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Valid Until'),
        help_text=_('When this announcement should stop being displayed (optional)')
    )
    
    class Meta:
        verbose_name = _('Announcement')
        verbose_name_plural = _('Announcements')
        ordering = ['-priority', '-created_at']
    
    def __str__(self):
        return f"{self.title} ({self.get_priority_display()})"
    
    @property
    def is_currently_valid(self):
        """Check if the announcement is currently valid based on date range"""
        now = timezone.now()
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        return True
    
    @property
    def is_displayed(self):
        """Check if the announcement should be displayed (active and valid)"""
        return self.is_active and self.is_currently_valid
    
    def get_priority_class(self):
        """Get Bootstrap CSS class for priority level"""
        priority_classes = {
            'low': 'info',
            'normal': 'primary',
            'high': 'warning',
            'urgent': 'danger',
        }
        return priority_classes.get(self.priority, 'primary')
