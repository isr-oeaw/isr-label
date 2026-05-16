import datetime
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, TemplateView, UpdateView, ListView, FormView

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied
from django.utils.translation import gettext_lazy as _, gettext
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .forms import (
    CustomUserCreationForm,
    CustomUserEditForm,
    RoleForm,
    RoleFilterForm,
    UserSettingsForm,
    UserNotificationForm,
    UserProfileForm,
    DataExportForm,
    SuperuserSetPasswordForm,
)
from .models import Role

CustomUser = get_user_model()


def _ensure_verified_email_for_approved_user(user):
    """
    When staff approves a user, mark their primary login email verified in allauth
    so the EmailAddress row matches the approved account.
    """
    if not getattr(user, "is_approved", False) or not user.email:
        return
    from allauth.account.models import EmailAddress

    email_norm = user.email.strip().lower()
    ea = EmailAddress.objects.filter(user=user, email__iexact=email_norm).first()
    if ea:
        EmailAddress.objects.filter(user=user, primary=True).exclude(pk=ea.pk).update(primary=False)
        update_fields = []
        if not ea.verified:
            ea.verified = True
            update_fields.append("verified")
        if not ea.primary:
            ea.primary = True
            update_fields.append("primary")
        if update_fields:
            ea.save(update_fields=update_fields)
        return
    EmailAddress.objects.filter(user=user).update(primary=False)
    EmailAddress.objects.create(
        user=user, email=email_norm, primary=True, verified=True
    )


def _setup_allauth_email_after_signup(request, user, *, created_by_admin):
    """Create allauth EmailAddress; send signup confirmation only if verification is enabled."""
    from allauth.account import app_settings as allauth_settings
    from allauth.account.internal.flows.email_verification import (
        send_verification_email_to_address,
    )
    from allauth.account.models import EmailAddress
    from allauth.account.utils import setup_user_email

    try:
        primary = setup_user_email(request, user, [])
    except AssertionError:
        primary = EmailAddress.objects.filter(user=user, primary=True).first()
    if not primary:
        return
    if created_by_admin:
        if not primary.verified:
            primary.verified = True
            primary.save()
    else:
        ev = allauth_settings.EMAIL_VERIFICATION
        if ev and str(ev).lower() != "none":
            send_verification_email_to_address(request, primary, signup=True)


def is_superuser_or_has_permission(permission):
    """Decorator to check if user is superuser or has specific permission"""
    def check_permission(user):
        return user.is_superuser or user.has_role_permission(permission)
    return user_passes_test(check_permission)


class AccountDeleteView(LoginRequiredMixin, DeleteView):
    model = get_user_model()
    template_name = 'user/confirm_delete.html'
    success_url = reverse_lazy('home')

    def get_object(self, queryset=None):
        # Ensure that only the logged-in user can delete their user
        return self.request.user

    def delete(self, request, *args, **kwargs):
        # Optionally, add a message for the user or perform extra cleanup
        messages.success(request, "Your user has been deleted successfully.")
        return super().delete(request, *args, **kwargs)





class SignupPageView(CreateView):
    form_class = CustomUserCreationForm
    success_url = reverse_lazy("home")
    template_name = "user/signup.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Check if the current user is an admin (superuser or has admin role)
        kwargs['created_by_admin'] = (
            self.request.user.is_authenticated and 
            (self.request.user.is_superuser or self.request.user.has_role_permission('admin'))
        )
        return kwargs

    def form_valid(self, form):
        user = form.save()
        _setup_allauth_email_after_signup(
            self.request, user, created_by_admin=form.created_by_admin
        )
        # If user was created by admin, show success message
        if form.created_by_admin:
            messages.success(
                self.request, 
                f'User {user.username} has been created and approved successfully.'
            )
        else:
            # If user was created by regular signup, show pending approval message
            messages.info(
                self.request, 
                f'Your account has been created successfully. Please wait for administrator approval before you can access all features.'
            )
        
        return super().form_valid(form)


def SettingsView(request):
    """
    Display user settings including profile and language preferences.
    If the user is not authenticated, display the login form.
    """
    if request.user.is_authenticated:
        # Initialize forms
        profile_form = UserProfileForm(instance=request.user)
        settings_form = UserSettingsForm(instance=request.user)
        notification_form = UserNotificationForm(instance=request.user)
        
        # Handle form submissions
        if request.method == 'POST':
            # Check which form was submitted
            if 'profile_submit' in request.POST:
                profile_form = UserProfileForm(request.POST, instance=request.user)
                if profile_form.is_valid():
                    profile_form.save()
                    messages.success(request, 'Your profile information has been updated successfully.')
                    return redirect('user-settings')
            
            elif 'language_submit' in request.POST:
                settings_form = UserSettingsForm(request.POST, instance=request.user)
                if settings_form.is_valid():
                    settings_form.save()
                    # Activate the new language immediately
                    from django.utils import translation
                    new_language = settings_form.cleaned_data.get('language')
                    if new_language:
                        translation.activate(new_language)
                        request.LANGUAGE_CODE = new_language
                    messages.success(request, 'Your language preference has been updated successfully.')
                    return redirect('user-settings')
            
            elif 'notifications_submit' in request.POST:
                notification_form = UserNotificationForm(request.POST, instance=request.user)
                if notification_form.is_valid():
                    notification_form.save()
                    messages.success(request, 'Your notification preferences have been updated successfully.')
                    return redirect('user-settings')
        
        context = {
            'user': request.user,
            'profile_form': profile_form,
            'settings_form': settings_form,
            'notification_form': notification_form,
        }
        return render(request, "user/settings.html", context)
    else:
        # Process the login form for unauthenticated users
        form = AuthenticationForm(request=request, data=request.POST or None)
        if request.method == "POST":
            if form.is_valid():
                user = form.get_user()
                login(request, user)
                return redirect("home")
        return render(request, "user/login.html", {"form": form})


@login_required
def data_export_view(request):
    """
    Handle data export requests for GDPR compliance
    """
    if request.method == 'POST':
        form = DataExportForm(request.POST)
        if form.is_valid():
            export_format = form.cleaned_data['format']
            include_datasets = form.cleaned_data['include_datasets']
            include_projects = form.cleaned_data['include_projects']
            include_activity = form.cleaned_data['include_activity']
            
            # Prepare user data for export
            user_data = {
                'user_info': {
                    'username': request.user.username,
                    'email': request.user.email,
                    'first_name': request.user.first_name,
                    'last_name': request.user.last_name,
                    'date_joined': request.user.date_joined.isoformat(),
                    'last_login': request.user.last_login.isoformat() if request.user.last_login else None,
                    'language': request.user.language,
                    'role': request.user.role.name if request.user.role else None,
                }
            }
            
            # Add datasets if requested
            if include_datasets:
                try:
                    from datasets.models import Dataset, DatasetVersion
                    user_datasets = []
                    datasets = Dataset.objects.filter(owner=request.user)
                    for dataset in datasets:
                        dataset_info = {
                            'title': dataset.title,
                            'description': dataset.description,
                            'abstract': dataset.abstract,
                            'status': dataset.status,
                            'created_at': dataset.created_at.isoformat(),
                            'updated_at': dataset.updated_at.isoformat(),
                            'download_count': dataset.download_count,
                            'view_count': dataset.view_count,
                        }
                        
                        # Add dataset versions
                        versions = DatasetVersion.objects.filter(dataset=dataset)
                        dataset_info['versions'] = [
                            {
                                'version_number': version.version_number,
                                'description': version.description,
                                'created_at': version.created_at.isoformat(),
                                'file_size': version.file_size,
                            }
                            for version in versions
                        ]
                        user_datasets.append(dataset_info)
                    
                    user_data['datasets'] = user_datasets
                except ImportError:
                    user_data['datasets'] = []
            
            # Add projects if requested
            if include_projects:
                try:
                    from projects.models import Project
                    user_projects = []
                    projects = Project.objects.filter(
                        Q(owner=request.user) | Q(memberships__user=request.user)
                    ).distinct()
                    for project in projects:
                        project_info = {
                            'title': project.title,
                            'description': project.description,
                            'abstract': project.abstract,
                            'status': project.status,
                            'access_level': project.access_level,
                            'created_at': project.created_at.isoformat(),
                            'updated_at': project.updated_at.isoformat(),
                            'is_owner': project.owner == request.user,
                        }
                        user_projects.append(project_info)
                    
                    user_data['projects'] = user_projects
                except ImportError:
                    user_data['projects'] = []
            
            # Add activity log if requested
            if include_activity:
                try:
                    from auditlog.models import LogEntry
                    # Get audit log entries for this user
                    log_entries = LogEntry.objects.filter(
                        content_type__model='customuser',
                        object_id=request.user.id
                    ).order_by('-timestamp')[:100]  # Limit to last 100 entries
                    
                    activity_log = [
                        {
                            'timestamp': entry.timestamp.isoformat(),
                            'action': entry.action,
                            'changes': entry.changes,
                        }
                        for entry in log_entries
                    ]
                    
                    user_data['activity_log'] = activity_log
                except ImportError:
                    user_data['activity_log'] = []
            
            # Generate response based on format
            from django.http import HttpResponse
            from datetime import datetime
            import json
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            if export_format == 'json':
                response = HttpResponse(
                    json.dumps(user_data, indent=2, ensure_ascii=False),
                    content_type='application/json'
                )
                response['Content-Disposition'] = f'attachment; filename="user_data_export_{timestamp}.json"'
            
            elif export_format == 'csv':
                import csv
                import io
                
                output = io.StringIO()
                writer = csv.writer(output)
                
                # Write user info
                writer.writerow(['Field', 'Value'])
                for key, value in user_data['user_info'].items():
                    writer.writerow([key, value])
                
                # Write datasets if included
                if 'datasets' in user_data:
                    writer.writerow([])
                    writer.writerow(['Dataset', 'Title', 'Status', 'Created'])
                    for dataset in user_data['datasets']:
                        writer.writerow(['', dataset['title'], dataset['status'], dataset['created_at']])
                
                response = HttpResponse(
                    output.getvalue(),
                    content_type='text/csv'
                )
                response['Content-Disposition'] = f'attachment; filename="user_data_export_{timestamp}.csv"'
            
            else:  # XML
                from django.utils.xmlutils import SimplerXMLGenerator
                import io
                
                output = io.StringIO()
                xml = SimplerXMLGenerator(output, 'utf-8')
                xml.startDocument()
                xml.startElement('user_data_export', {})
                
                # User info
                xml.startElement('user_info', {})
                for key, value in user_data['user_info'].items():
                    xml.startElement(key, {})
                    xml.characters(str(value) if value is not None else '')
                    xml.endElement(key)
                xml.endElement('user_info')
                
                # Datasets
                if 'datasets' in user_data:
                    xml.startElement('datasets', {})
                    for dataset in user_data['datasets']:
                        xml.startElement('dataset', {})
                        for key, value in dataset.items():
                            if key != 'versions':
                                xml.startElement(key, {})
                                xml.characters(str(value) if value is not None else '')
                                xml.endElement(key)
                        xml.endElement('dataset')
                    xml.endElement('datasets')
                
                xml.endElement('user_data_export')
                xml.endDocument()
                
                response = HttpResponse(
                    output.getvalue(),
                    content_type='application/xml'
                )
                response['Content-Disposition'] = f'attachment; filename="user_data_export_{timestamp}.xml"'
            
            return response
    
    else:
        form = DataExportForm()
    
    return render(request, 'user/data_export.html', {'form': form})


class UsersUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = get_user_model()
    form_class = CustomUserEditForm
    template_name = 'user/edit.html'
    pk_url_kwarg = 'user_id'

    def get_success_url(self):
        return reverse_lazy('user-management')

    def test_func(self):
        # Allow access if user is superuser, has user.edit permission, or has Administrator role
        return (
            self.request.user.is_superuser or 
            self.request.user.has_role_permission('user.edit') or
            (self.request.user.role and self.request.user.role.name == 'Administrator')
        )
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Only superusers can modify staff and superuser privileges
        if not self.request.user.is_superuser:
            form.fields['is_staff'].widget.attrs['disabled'] = True
            form.fields['is_superuser'].widget.attrs['disabled'] = True
            # Add help text to inform users why fields are disabled
            form.fields['is_staff'].help_text = _('Only superusers can modify staff privileges.')
            form.fields['is_superuser'].help_text = _('Only superusers can modify superuser privileges.')
        return form
    
    def form_valid(self, form):
        # Security check: Only superusers can assign superuser privileges
        if form.cleaned_data.get('is_superuser') and not self.request.user.is_superuser:
            form.add_error('is_superuser', _('Only superusers can assign superuser privileges.'))
            return self.form_invalid(form)
        
        # Security check: Only superusers can assign staff privileges
        if form.cleaned_data.get('is_staff') and not self.request.user.is_superuser:
            form.add_error('is_staff', _('Only superusers can assign staff privileges.'))
            return self.form_invalid(form)
        
        # Prevent users from removing their own superuser status
        if (self.object == self.request.user and 
            self.object.is_superuser and 
            not form.cleaned_data.get('is_superuser')):
            form.add_error('is_superuser', _('You cannot remove your own superuser privileges.'))
            return self.form_invalid(form)
        
        response = super().form_valid(form)
        if self.object.is_approved:
            _ensure_verified_email_for_approved_user(self.object)
        return response


class SuperuserSetUserPasswordView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    form_class = SuperuserSetPasswordForm
    template_name = 'user/admin_set_password.html'

    def test_func(self):
        return self.request.user.is_superuser

    def dispatch(self, request, *args, **kwargs):
        self.target_user = get_object_or_404(CustomUser, pk=kwargs['user_id'])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.target_user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['target_user'] = self.target_user
        return context

    def form_valid(self, form):
        form.save()
        messages.success(
            self.request,
            gettext('Password updated for %(username)s.') % {'username': self.target_user.username},
        )
        return redirect('user-management')


class AdminUserDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Delete another user account (from user management / edit flow)."""

    model = CustomUser
    template_name = 'user/admin_confirm_delete_user.html'
    pk_url_kwarg = 'user_id'
    context_object_name = 'target_user'

    def test_func(self):
        return (
            self.request.user.is_superuser
            or self.request.user.has_role_permission('user.edit')
            or (self.request.user.role and self.request.user.role.name == 'Administrator')
        )

    def get_success_url(self):
        return reverse_lazy('user-management')

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if obj.pk == self.request.user.pk:
            raise PermissionDenied(
                gettext(
                    'You cannot delete your own account from this page. Use account settings instead.'
                )
            )
        if obj.is_superuser and not self.request.user.is_superuser:
            raise PermissionDenied(
                gettext('Only superusers can delete another superuser account.')
            )
        return obj

    def form_valid(self, form):
        user_id = self.object.pk
        username = self.object.username
        try:
            self.object.delete()
        except ProtectedError:
            messages.error(
                self.request,
                gettext(
                    'Cannot delete user "%(name)s" while other data still references them '
                    '(for example projects they own, memberships, or labeling data). '
                    'Transfer project ownership, remove related records, or delete those projects first.'
                )
                % {'name': username},
            )
            return redirect('user-edit', user_id=user_id)
        messages.success(
            self.request,
            gettext('User "%(name)s" has been deleted.') % {'name': username},
        )
        return redirect('user-management')


class UserManagementView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = get_user_model()
    context_object_name = 'users'
    template_name = 'user/management.html'
    paginate_by = 20

    def test_func(self):
        # Allow access if user is superuser or has Administrator role
        return (
            self.request.user.is_superuser or 
            (self.request.user.role and self.request.user.role.name == 'Administrator')
        )

    def get_queryset(self):
        queryset = CustomUser.objects.select_related('role').all().order_by('username')

        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(username__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query)
            )

        role_filter = self.request.GET.get('role', '')
        if role_filter:
            queryset = queryset.filter(role__name=role_filter)

        status_filter = self.request.GET.get('status', '')
        if status_filter == 'active':
            queryset = queryset.filter(is_active=True)
        elif status_filter == 'inactive':
            queryset = queryset.filter(is_active=False)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['roles'] = Role.objects.filter(is_active=True)
        context['search_query'] = self.request.GET.get('search', '')
        context['role_filter'] = self.request.GET.get('role', '')
        context['status_filter'] = self.request.GET.get('status', '')
        User = get_user_model()
        context['total_users'] = User.objects.count()
        context['active_users'] = User.objects.filter(is_active=True).count()
        context['inactive_users'] = User.objects.filter(is_active=False).count()
        context['users_with_roles'] = User.objects.filter(role__isnull=False).count()
        context['users_without_roles'] = User.objects.filter(role__isnull=True).count()
        context['total_roles'] = Role.objects.count()
        context['active_roles'] = Role.objects.filter(is_active=True).count()
        return context


class UserCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = get_user_model()
    form_class = CustomUserCreationForm
    template_name = 'user/user_form.html'
    success_url = reverse_lazy('user-management')

    def test_func(self):
        # Allow access if user is superuser or has Administrator role
        return (
            self.request.user.is_superuser or 
            (self.request.user.role and self.request.user.role.name == 'Administrator')
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Since this is an admin view, mark as created by admin
        kwargs['created_by_admin'] = True
        return kwargs

    def form_valid(self, form):
        user = form.save()
        _setup_allauth_email_after_signup(
            self.request, user, created_by_admin=True
        )
        messages.success(
            self.request, 
            f'User {user.username} has been created and approved successfully.'
        )
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)


class PendingUsersView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """View for administrators to see and approve pending users"""
    model = get_user_model()
    template_name = 'user/pending_users.html'
    context_object_name = 'pending_users'
    paginate_by = 20

    def test_func(self):
        # Allow access if user is superuser, has admin role, or has Administrator role
        return (
            self.request.user.is_superuser or 
            self.request.user.has_role_permission('admin') or
            (self.request.user.role and self.request.user.role.name == 'Administrator')
        )

    def get_queryset(self):
        return CustomUser.objects.filter(is_approved=False).order_by('date_joined')


@login_required
@user_passes_test(lambda u: u.is_superuser or u.has_role_permission('admin'))
def approve_user(request, user_id):
    """Approve a pending user"""
    user = get_object_or_404(CustomUser, id=user_id, is_approved=False)
    
    if request.method == 'POST':
        user.is_approved = True
        user.save()
        _ensure_verified_email_for_approved_user(user)
        messages.success(
            request, 
            f'User {user.username} has been approved successfully.'
        )
        return redirect('pending-users')
    
    return render(request, 'user/approve_user_confirm.html', {'user': user})


@login_required
@user_passes_test(lambda u: u.is_superuser or u.has_role_permission('admin'))
def reject_user(request, user_id):
    """Reject a pending user (delete their account)"""
    user = get_object_or_404(CustomUser, id=user_id, is_approved=False)
    
    if request.method == 'POST':
        username = user.username
        user.delete()
        messages.success(
            request, 
            f'User {username} has been rejected and their account has been deleted.'
        )
        return redirect('pending-users')
    
    return render(request, 'user/reject_user_confirm.html', {'user': user})


# Role Management Views
class RoleListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Role
    context_object_name = 'roles'
    template_name = 'user/role_list.html'
    paginate_by = 20

    def test_func(self):
        # Allow access if user is superuser or has Administrator role
        return (
            self.request.user.is_superuser or 
            (self.request.user.role and self.request.user.role.name == 'Administrator')
        )

    def get_queryset(self):
        queryset = Role.objects.all().order_by('name')
        
        # Filter by search query
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        
        # Filter by status
        status_filter = self.request.GET.get('status', '')
        if status_filter == 'active':
            queryset = queryset.filter(is_active=True)
        elif status_filter == 'inactive':
            queryset = queryset.filter(is_active=False)
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['status_filter'] = self.request.GET.get('status', '')
        return context


class RoleCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Role
    form_class = RoleForm
    template_name = 'user/role_form.html'
    success_url = reverse_lazy('role-list')

    def test_func(self):
        # Allow access if user is superuser or has Administrator role
        return (
            self.request.user.is_superuser or 
            (self.request.user.role and self.request.user.role.name == 'Administrator')
        )

    def form_valid(self, form):
        messages.success(self.request, f"Role '{form.instance.name}' created successfully.")
        return super().form_valid(form)


class RoleUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Role
    form_class = RoleForm
    template_name = 'user/role_form.html'
    success_url = reverse_lazy('role-list')

    def test_func(self):
        # Allow access if user is superuser or has Administrator role
        return (
            self.request.user.is_superuser or 
            (self.request.user.role and self.request.user.role.name == 'Administrator')
        )

    def form_valid(self, form):
        messages.success(self.request, f"Role '{form.instance.name}' updated successfully.")
        return super().form_valid(form)


class RoleDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Role
    template_name = 'user/role_confirm_delete.html'
    success_url = reverse_lazy('role-list')

    def test_func(self):
        # Allow access if user is superuser or has Administrator role
        return (
            self.request.user.is_superuser or 
            (self.request.user.role and self.request.user.role.name == 'Administrator')
        )

    def delete(self, request, *args, **kwargs):
        role = self.get_object()
        messages.success(request, f"Role '{role.name}' deleted successfully.")
        return super().delete(request, *args, **kwargs)


class UserProfileView(LoginRequiredMixin, TemplateView):
    """Display user profile with projects and datasets"""
    template_name = 'user/profile.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_id = kwargs.get('user_id')
        
        # Get the user to display profile for
        if user_id:
            profile_user = get_object_or_404(CustomUser, id=user_id)
        else:
            profile_user = self.request.user
        
        # Check if current user can view this profile
        can_view = (
            self.request.user == profile_user or  # Own profile
            self.request.user.is_superuser or     # Superuser can view all
            self.request.user.has_role_permission('user.view')  # Has view permission
        )
        
        if not can_view:
            raise PermissionDenied("You don't have permission to view this profile.")
        
        # Get user's projects
        from projects.models import Project
        from labeling.models import LabelDataset, Task

        user_projects = Project.objects.filter(
            Q(owner=profile_user) | Q(memberships__user=profile_user)
        ).distinct().select_related('owner').prefetch_related('memberships__user')

        user_label_datasets_qs = (
            LabelDataset.objects.filter(
                Q(project__owner=profile_user)
                | Q(project__memberships__user=profile_user)
            )
            .select_related("project")
            .prefetch_related("images")
            .distinct()
            .order_by("-updated_at")
        )
        label_tasks_in_projects = Task.objects.filter(
            project__in=user_projects
        ).count()

        context.update(
            {
                "profile_user": profile_user,
                "user_projects": user_projects,
                "user_label_datasets": user_label_datasets_qs[:25],
                "user_label_datasets_count": user_label_datasets_qs.count(),
                "user_label_tasks_count": label_tasks_in_projects,
                "is_own_profile": self.request.user == profile_user,
            }
        )
        
        return context


@require_POST
def resend_email_verification(request):
    """Resend email verification for the current user or session user"""
    try:
        from allauth.account.models import EmailAddress
        
        # Try to get user from different sources
        user = None
        
        # Method 1: Check if user is authenticated
        if request.user.is_authenticated:
            user = request.user
        
        # Method 2: Check session for user ID
        if not user:
            user_id = request.session.get('_auth_user_id')
            if user_id:
                try:
                    user = CustomUser.objects.get(id=user_id)
                except CustomUser.DoesNotExist:
                    pass
        
        # Method 3: Check for email in session (allauth sometimes stores this)
        if not user:
            email = request.session.get('account_verified_email')
            if email:
                try:
                    email_address = EmailAddress.objects.get(email=email, verified=False)
                    user = email_address.user
                except EmailAddress.DoesNotExist:
                    pass
        
        # Method 4: Check for temporary user in session
        if not user:
            temp_user_id = request.session.get('temp_user_id')
            if temp_user_id:
                try:
                    user = CustomUser.objects.get(id=temp_user_id)
                except CustomUser.DoesNotExist:
                    pass
        
        # Method 5: Try to get from request JSON data if available
        if not user:
            try:
                import json
                data = json.loads(request.body)
                email = data.get('email')
                if email:
                    try:
                        email_address = EmailAddress.objects.get(email=email, verified=False)
                        user = email_address.user
                    except EmailAddress.DoesNotExist:
                        pass
            except (json.JSONDecodeError, AttributeError):
                pass
        
        if not user:
            # Log session data for debugging
            import logging
            logger = logging.getLogger('email')
            logger.error(f"Could not find user for resend verification. Session keys: {list(request.session.keys())}")
            logger.error(f"Session data: {dict(request.session)}")
            logger.error(f"User authenticated: {request.user.is_authenticated}")
            logger.error(f"User: {request.user}")
            
            return JsonResponse({
                'success': False, 
                'message': 'User not found. Please try logging in again.'
            }, status=404)
        
        # Get the user's primary email address
        email_address = EmailAddress.objects.get(
            user=user, 
            email=user.email
        )
        
        # Check if email is already verified
        if email_address.verified:
            return JsonResponse({
                'success': False, 
                'message': 'Email is already verified'
            }, status=400)
        
        # Send email confirmation
        email_address.send_confirmation(request)
        
        # Log the email sending for debugging
        import logging
        logger = logging.getLogger('email')
        logger.info(f"Email verification resent for user {user.username} ({user.email})")
        
        return JsonResponse({
            'success': True, 
            'message': 'Verification email sent successfully'
        })
        
    except EmailAddress.DoesNotExist:
        return JsonResponse({
            'success': False, 
            'message': 'Email address not found'
        }, status=404)
    except Exception as e:
        # Log the full error for debugging
        import logging
        logger = logging.getLogger('email')
        logger.error(f"Error in resend_email_verification: {str(e)}")
        logger.error(f"Exception type: {type(e)}")
        
        return JsonResponse({
            'success': False, 
            'message': f'Error sending email: {str(e)}'
        }, status=500)
