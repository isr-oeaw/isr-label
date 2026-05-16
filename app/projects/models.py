from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.urls import reverse

User = get_user_model()


class ProjectMembership(models.Model):
    """User membership in a project with a labeling role."""
    class Role(models.TextChoices):
        ADMIN = 'admin', _('Admin')
        REVIEWER = 'reviewer', _('Reviewer')
        ANNOTATOR = 'annotator', _('Annotator')
        VIEWER = 'viewer', _('Viewer')

    project = models.ForeignKey(
        'Project',
        on_delete=models.CASCADE,
        related_name='memberships',
        verbose_name=_('Project'),
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='project_memberships',
        verbose_name=_('User'),
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.ANNOTATOR,
        verbose_name=_('Role'),
    )
    joined_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Joined at'))

    class Meta:
        unique_together = [('project', 'user')]
        ordering = ['project', 'user']
        verbose_name = _('Project membership')
        verbose_name_plural = _('Project memberships')
        indexes = [
            models.Index(fields=['project', 'user']),
        ]

    def __str__(self):
        return f'{self.user} @ {self.project} ({self.get_role_display()})'


class Project(models.Model):
    """Model representing a research project and labeling container."""

    STATUS_CHOICES = [
        ('planning', _('Planning')),
        ('active', _('Active')),
        ('completed', _('Completed')),
        ('on_hold', _('On Hold')),
        ('cancelled', _('Cancelled')),
    ]

    ACCESS_LEVEL_CHOICES = [
        ('public', _('Public')),
        ('restricted', _('Restricted')),
        ('private', _('Private')),
    ]

    # Basic Information
    title = models.CharField(
        max_length=200,
        verbose_name=_('Project Title'),
        help_text=_('Name of the research project')
    )
    description = models.TextField(
        verbose_name=_('Description'),
        help_text=_('Detailed description of the project objectives and scope')
    )
    abstract = models.TextField(
        blank=True,
        verbose_name=_('Abstract'),
        help_text=_('Brief summary of the project')
    )

    # Project Details
    start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Start Date'),
        help_text=_('Project start date')
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('End Date'),
        help_text=_('Project end date')
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='planning',
        verbose_name=_('Status')
    )
    access_level = models.CharField(
        max_length=20,
        choices=ACCESS_LEVEL_CHOICES,
        default='private',
        verbose_name=_('Access Level')
    )

    # Ownership
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='owned_projects',
        verbose_name=_('Project Owner'),
        help_text=_('User who owns and manages this project')
    )

    # Project Metadata
    keywords = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('Keywords'),
        help_text=_('Comma-separated keywords for the project')
    )
    tags = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('Tags'),
        help_text=_('Comma-separated tags for categorization')
    )

    # External References
    project_url = models.URLField(
        blank=True,
        verbose_name=_('Project URL'),
        help_text=_('External URL to project website or repository')
    )
    funding_source = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_('Funding Source'),
        help_text=_('Organization or agency funding this project')
    )
    grant_number = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Grant Number'),
        help_text=_('Grant or contract number')
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Project')
        verbose_name_plural = _('Projects')
        permissions = [
            ('can_manage_projects', 'Can manage all projects'),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('projects:project_detail', kwargs={'pk': self.pk})

    @property
    def duration_days(self):
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days
        return None

    @property
    def is_active(self):
        return self.status == 'active'

    @property
    def is_completed(self):
        return self.status == 'completed'

    def get_membership(self, user):
        if not user or not user.is_authenticated:
            return None
        return self.memberships.filter(user_id=user.id).select_related('user').first()

    def is_member(self, user):
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or user == self.owner:
            return True
        return self.memberships.filter(user_id=user.id).exists()

    def can_edit(self, user):
        """Project metadata: owner, admin/reviewer/annotator members, or superuser."""
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or user == self.owner:
            return True
        m = self.get_membership(user)
        if m and m.role != ProjectMembership.Role.VIEWER:
            return True
        return False

    def is_accessible_by(self, user):
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or self.is_member(user):
            return True
        if self.access_level == 'public':
            return True
        if self.access_level == 'restricted' and user.has_perm('projects.can_manage_projects'):
            return True
        return False

    def get_keywords_list(self):
        if self.keywords:
            return [k.strip() for k in self.keywords.split(',') if k.strip()]
        return []

    def get_tags_list(self):
        if self.tags:
            return [t.strip() for t in self.tags.split(',') if t.strip()]
        return []

    def delete(self, *args, **kwargs):
        # Tasks use PROTECT to image/schema; remove them first so CASCADE from
        # project can delete LabelDataset / LabelSchema / ImageAsset rows.
        from django.db import transaction

        from labeling.models import Task

        with transaction.atomic():
            Task.objects.filter(project_id=self.pk).delete()
            super().delete(*args, **kwargs)


def ensure_owner_membership(project):
    """Owner always has an admin ProjectMembership row."""
    ProjectMembership.objects.get_or_create(
        project=project,
        user=project.owner,
        defaults={'role': ProjectMembership.Role.ADMIN},
    )
    m = project.memberships.filter(user=project.owner).first()
    if m and m.role != ProjectMembership.Role.ADMIN:
        m.role = ProjectMembership.Role.ADMIN
        m.save(update_fields=['role'])


