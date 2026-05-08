from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import (
    CreateView, DeleteView, DetailView, FormView, ListView, TemplateView, UpdateView,
)

from .forms import (
    ProjectFilterForm,
    ProjectForm,
    ProjectMemberInviteForm,
    ProjectMemberRoleForm,
    ProjectTransferOwnershipForm,
)
from .models import Project, ProjectMembership, ensure_owner_membership

User = get_user_model()


def _is_project_admin(user, project):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if project.owner_id == user.id:
        return True
    m = project.get_membership(user)
    return m and m.role == ProjectMembership.Role.ADMIN


class EditorOrAdministratorMixin(UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if user.role and user.role.is_active and user.role.name in ['Editor', 'Administrator']:
            return True
        return False

    def handle_no_permission(self):
        messages.error(
            self.request,
            'Access denied. Only Editors and Administrators can create projects.',
        )
        return redirect('projects:project_list')


class ProjectListView(LoginRequiredMixin, ListView):
    model = Project
    template_name = 'projects/project_list.html'
    context_object_name = 'projects'
    paginate_by = 20

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = ProjectFilterForm(self.request.GET)
        context['search_query'] = self.request.GET.get('search', '')
        context['selected_status'] = self.request.GET.get('status', '')
        return context

    def get_queryset(self):
        u = self.request.user
        qs = Project.objects.select_related('owner').prefetch_related('memberships__user')
        search = self.request.GET.get('search')
        status = self.request.GET.get('status')
        if not u.is_superuser:
            qs = qs.filter(
                Q(owner=u) | Q(memberships__user=u) | Q(access_level='public')
            ).distinct()
        if search:
            qs = qs.filter(
                Q(title__icontains=search)
                | Q(description__icontains=search)
                | Q(abstract__icontains=search)
                | Q(keywords__icontains=search)
                | Q(tags__icontains=search)
            )
        if status:
            qs = qs.filter(status=status)
        return qs.order_by('-created_at')


class ProjectDetailView(LoginRequiredMixin, DetailView):
    model = Project
    template_name = 'projects/project_detail.html'
    context_object_name = 'project'

    def get_queryset(self):
        return Project.objects.select_related('owner').prefetch_related(
            'memberships__user',
            'labeling_datasets',
        )

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if not obj.is_accessible_by(self.request.user):
            raise Http404("Project not found or access denied")
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        p = self.object
        u = self.request.user
        context['can_edit'] = p.can_edit(u)
        context['is_project_member'] = p.is_member(u)
        return context


class ProjectCreateView(LoginRequiredMixin, EditorOrAdministratorMixin, CreateView):
    model = Project
    form_class = ProjectForm
    template_name = 'projects/project_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.owner = self.request.user
        response = super().form_valid(form)
        ensure_owner_membership(self.object)
        messages.success(
            self.request,
            f'Project "{self.object.title}" has been created successfully.',
        )
        return response

    def get_success_url(self):
        return reverse_lazy('projects:project_detail', kwargs={'pk': self.object.pk})


class ProjectUpdateView(LoginRequiredMixin, UpdateView):
    model = Project
    form_class = ProjectForm
    template_name = 'projects/project_form.html'

    def get_queryset(self):
        u = self.request.user
        if u.is_superuser:
            return Project.objects.all()
        return Project.objects.filter(
            Q(owner=u)
            | Q(
                memberships__user=u,
                memberships__role__in=[
                    ProjectMembership.Role.ADMIN,
                    ProjectMembership.Role.REVIEWER,
                    ProjectMembership.Role.ANNOTATOR,
                ],
            )
        ).distinct()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        ensure_owner_membership(self.object)
        messages.success(
            self.request,
            f'Project "{self.object.title}" has been updated successfully.',
        )
        return response

    def get_success_url(self):
        return reverse_lazy('projects:project_detail', kwargs={'pk': self.object.pk})


class ProjectDeleteView(LoginRequiredMixin, DeleteView):
    model = Project
    template_name = 'projects/project_confirm_delete.html'
    success_url = reverse_lazy('projects:project_list')

    def get_queryset(self):
        return Project.objects.filter(owner=self.request.user)

    def delete(self, request, *args, **kwargs):
        project = self.get_object()
        title = project.title
        response = super().delete(request, *args, **kwargs)
        messages.success(request, _('Project "%(t)s" has been deleted successfully.') % {'t': title})
        return response


class ProjectTransferOwnershipView(LoginRequiredMixin, UpdateView):
    model = Project
    form_class = ProjectTransferOwnershipForm
    template_name = 'projects/project_transfer_ownership.html'

    def get_queryset(self):
        return Project.objects.filter(owner=self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.pop('instance', None)
        kwargs['current_user'] = self.request.user
        kwargs['project'] = self.get_object()
        return kwargs

    def form_valid(self, form):
        project = self.get_object()
        new_owner = form.cleaned_data['new_owner']
        current = self.request.user
        project.owner = new_owner
        project.save()
        ensure_owner_membership(project)
        ProjectMembership.objects.update_or_create(
            project=project,
            user=current,
            defaults={'role': ProjectMembership.Role.ANNOTATOR},
        )
        ProjectMembership.objects.filter(project=project, user=new_owner).update(
            role=ProjectMembership.Role.ADMIN
        )
        ensure_owner_membership(project)
        messages.success(
            self.request,
            _('Ownership transferred. You remain a member with annotator role (adjust on Team page if needed).'),
        )
        return redirect('projects:project_detail', pk=project.pk)

    def get_success_url(self):
        return reverse_lazy('projects:project_detail', kwargs={'pk': self.object.pk})


from django.utils.translation import gettext as _


class ProjectMembersView(LoginRequiredMixin, TemplateView):
    """List members; invite only for project admins."""
    template_name = 'projects/project_members.html'

    def get_project(self):
        p = get_object_or_404(
            Project.objects.select_related('owner').prefetch_related('memberships__user'),
            pk=self.kwargs['pk'],
        )
        if not p.is_accessible_by(self.request.user):
            raise Http404()
        return p

    def get(self, request, *args, **kwargs):
        p = self.get_project()
        can_manage = _is_project_admin(request.user, p)
        form = ProjectMemberInviteForm() if can_manage else None
        return self._render(p, form)

    def post(self, request, *args, **kwargs):
        p = self.get_project()
        if not _is_project_admin(request.user, p):
            return HttpResponseForbidden()
        form = ProjectMemberInviteForm(request.POST)
        if not form.is_valid():
            return self._render(p, form)
        email = form.cleaned_data['email'].strip().lower()
        role = form.cleaned_data['role']
        try:
            u = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            form.add_error('email', _('No user with this email. They must sign up first.'))
            return self._render(p, form)
        if u.id == p.owner_id:
            messages.warning(request, _('Owner is already a member (admin).'))
            return redirect('projects:project_members', pk=p.pk)
        ProjectMembership.objects.update_or_create(
            project=p, user=u, defaults={'role': role}
        )
        messages.success(request, _('Member %(e)s added or updated.') % {'e': email})
        return redirect('projects:project_members', pk=p.pk)

    def _render(self, project, form):
        from django.template.response import TemplateResponse
        u = self.request.user
        return TemplateResponse(
            self.request,
            self.template_name,
            {
                'project': project,
                'members': project.memberships.all().order_by('role', 'user__username'),
                'form': form,
                'can_manage': _is_project_admin(u, project),
            },
        )


class ProjectMemberRemoveView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        p = get_object_or_404(Project, pk=self.kwargs['pk'])
        return _is_project_admin(self.request.user, p)

    def post(self, request, pk, user_id):
        project = get_object_or_404(Project, pk=pk)
        if not _is_project_admin(request.user, project):
            return HttpResponseForbidden()
        if int(user_id) == project.owner_id:
            messages.error(request, _('Cannot remove the project owner. Transfer ownership first.'))
            return redirect('projects:project_members', pk=pk)
        ProjectMembership.objects.filter(project=project, user_id=user_id).delete()
        messages.success(request, _('Member removed.'))
        return redirect('projects:project_members', pk=pk)


class ProjectMemberUpdateRoleView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = ProjectMembership
    form_class = ProjectMemberRoleForm
    template_name = 'projects/project_member_edit.html'

    def get_queryset(self):
        return ProjectMembership.objects.filter(project_id=self.kwargs['pk'])

    def get_object(self, queryset=None):
        return get_object_or_404(
            self.get_queryset(), user_id=self.kwargs['user_id']
        )

    def test_func(self):
        p = get_object_or_404(Project, pk=self.kwargs['pk'])
        return _is_project_admin(self.request.user, p)

    def form_valid(self, form):
        p = get_object_or_404(Project, pk=self.kwargs['pk'])
        m = self.object
        if m.user_id == p.owner_id:
            m.role = ProjectMembership.Role.ADMIN
            m.save(update_fields=['role'])
        else:
            m.role = form.cleaned_data['role']
            m.save(update_fields=['role'])
        messages.success(self.request, _('Role updated.'))
        return redirect('projects:project_members', pk=p.pk)
