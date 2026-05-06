import logging
import requests
import json
from datetime import datetime, timedelta

from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone

logger = logging.getLogger(__name__)


class HomePageView(LoginRequiredMixin, TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['host'] = self.request.get_host()
        context['API_URL'] = settings.API_URL
        
        # Dashboard stats: labeling + projects (no legacy datasets app)
        from user.models import CustomUser
        from projects.models import Project
        from labeling.models import ImageAsset, LabelDataset

        thirty_days_ago = timezone.now() - timedelta(days=30)
        total_label_datasets = LabelDataset.objects.count()
        total_images = ImageAsset.objects.count()
        total_users = CustomUser.objects.filter(is_active=True).count()
        total_projects = Project.objects.count()

        recent_images = (
            ImageAsset.objects.filter(created_at__gte=thirty_days_ago)
            .select_related("dataset", "dataset__project")
            .order_by("-created_at")[:10]
        )
        popular_label_datasets = (
            LabelDataset.objects.annotate(ni=Count("images"))
            .select_related("project")
            .order_by("-ni", "-updated_at")[:5]
        )
        recent_projects = (
            Project.objects.select_related("owner")
            .order_by("-created_at")[:6]
        )

        user_label_datasets = []
        if self.request.user.is_authenticated:
            u = self.request.user
            user_label_datasets = list(
                LabelDataset.objects.filter(
                    Q(project__owner=u) | Q(project__memberships__user=u)
                )
                .select_related("project")
                .prefetch_related("images")
                .distinct()
                .order_by("-updated_at")[:5]
            )

        context.update(
            {
                "total_datasets": total_label_datasets,
                "total_images": total_images,
                "total_users": total_users,
                "total_projects": total_projects,
                "uptime_percentage": 99.9,
                "recent_images": recent_images,
                "popular_label_datasets": popular_label_datasets,
                "recent_projects": recent_projects,
                "user_label_datasets": user_label_datasets,
                "thirty_days_ago": thirty_days_ago,
            }
        )
        
        # Check if help section should be shown (only for 7 days after first login)
        show_help_section = False
        if self.request.user.is_authenticated and self.request.user.first_login_date:
            days_since_first_login = (timezone.now() - self.request.user.first_login_date).days
            show_help_section = days_since_first_login <= 7
        
        context['show_help_section'] = show_help_section
        
        # Get active announcements
        try:
            from .models import Announcement
            active_announcements = Announcement.objects.filter(
                is_active=True
            ).filter(
                Q(valid_until__isnull=True) | Q(valid_until__gt=timezone.now())
            ).filter(
                valid_from__lte=timezone.now()
            ).select_related('created_by').order_by('-priority', '-created_at')
            
            context['active_announcements'] = active_announcements
        except ImportError:
            context['active_announcements'] = []
        
        # Add group membership data for the current user (keeping existing functionality)
        if self.request.user.is_authenticated:
            try:
                from group.models import GroupMember
                from local.models import Local, Council
                
                # Get user's group memberships
                group_memberships = GroupMember.objects.filter(
                    user=self.request.user,
                    is_active=True
                ).select_related(
                    'group',
                    'group__party',
                    'group__party__local'
                ).order_by('group__name')
                
                context['group_memberships'] = group_memberships
                
                # Get unique locals and councils from memberships
                locals_from_memberships = set()
                councils_from_memberships = set()
                
                for membership in group_memberships:
                    if membership.group.party and membership.group.party.local:
                        locals_from_memberships.add(membership.group.party.local)
                        if hasattr(membership.group.party.local, 'council') and membership.group.party.local.council:
                            councils_from_memberships.add(membership.group.party.local.council)
                
                context['locals_from_memberships'] = sorted(locals_from_memberships, key=lambda x: x.name)
                context['councils_from_memberships'] = sorted(councils_from_memberships, key=lambda x: x.name)
                
            except ImportError:
                # If models are not available, set empty lists
                context['group_memberships'] = []
                context['locals_from_memberships'] = []
                context['councils_from_memberships'] = []
        else:
            context['group_memberships'] = []
            context['locals_from_memberships'] = []
            context['councils_from_memberships'] = []
        
        return context


class DocumentationView(TemplateView):
    """Documentation page view"""
    template_name = "documentation.html"


class AnnouncementManagementView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """
    View for managing announcements - only accessible by administrators
    """
    template_name = 'pages/announcement_management.html'
    context_object_name = 'announcements'
    paginate_by = 20
    
    def test_func(self):
        """Only superusers and users with admin role permission can access"""
        return (
            self.request.user.is_superuser or
            self.request.user.has_role_permission('admin')
        )
    
    def get_queryset(self):
        """Get all announcements ordered by priority and creation date"""
        from .models import Announcement
        return Announcement.objects.select_related('created_by').order_by('-priority', '-created_at')
    
    @property
    def model(self):
        """Get the Announcement model"""
        from .models import Announcement
        return Announcement
    
    def get_context_data(self, **kwargs):
        """Add additional context data"""
        # Set up view attributes for proper context generation
        if not hasattr(self, 'kwargs'):
            self.kwargs = {}
        if not hasattr(self, 'object_list'):
            self.object_list = self.get_queryset()
        
        context = super().get_context_data(**kwargs)
        
        # Add statistics
        from .models import Announcement
        context['total_announcements'] = Announcement.objects.count()
        context['active_announcements'] = Announcement.objects.filter(is_active=True).count()
        context['expired_announcements'] = Announcement.objects.filter(
            valid_until__lt=timezone.now()
        ).count()
        context['future_announcements'] = Announcement.objects.filter(
            valid_from__gt=timezone.now()
        ).count()
        
        return context


class AnnouncementCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """
    View for creating new announcements
    """
    model = None  # Will be set in __init__
    template_name = 'pages/announcement_form.html'
    fields = ['title', 'message', 'priority', 'is_active', 'valid_from', 'valid_until']
    success_url = reverse_lazy('announcement-management')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import Announcement
        self.model = Announcement
    
    def test_func(self):
        """Only superusers and users with admin role permission can access"""
        return (
            self.request.user.is_superuser or
            self.request.user.has_role_permission('admin')
        )
    
    def form_valid(self, form):
        """Set the created_by field to current user"""
        form.instance.created_by = self.request.user
        messages.success(self.request, f'Announcement "{form.instance.title}" has been created successfully.')
        return super().form_valid(form)


class AnnouncementUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """
    View for updating existing announcements
    """
    model = None  # Will be set in __init__
    template_name = 'pages/announcement_form.html'
    fields = ['title', 'message', 'priority', 'is_active', 'valid_from', 'valid_until']
    success_url = reverse_lazy('announcement-management')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import Announcement
        self.model = Announcement
    
    def test_func(self):
        """Only superusers and users with admin role permission can access"""
        return (
            self.request.user.is_superuser or
            self.request.user.has_role_permission('admin')
        )
    
    def form_valid(self, form):
        """Show success message"""
        messages.success(self.request, f'Announcement "{form.instance.title}" has been updated successfully.')
        return super().form_valid(form)


class AnnouncementDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """
    View for deleting announcements
    """
    model = None  # Will be set in __init__
    template_name = 'pages/announcement_confirm_delete.html'
    success_url = reverse_lazy('announcement-management')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import Announcement
        self.model = Announcement
    
    def test_func(self):
        """Only superusers and users with admin role permission can access"""
        return (
            self.request.user.is_superuser or
            self.request.user.has_role_permission('admin')
        )
    
    def delete(self, request, *args, **kwargs):
        """Show success message"""
        announcement = self.get_object()
        messages.success(request, f'Announcement "{announcement.title}" has been deleted successfully.')
        return super().delete(request, *args, **kwargs)