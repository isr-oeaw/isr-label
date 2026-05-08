import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext as _
from django.views.generic import CreateView, DetailView, FormView, ListView, TemplateView, UpdateView

from projects.models import Project, ProjectMembership
from .forms import LabelDatasetForm, LabelSchemaEditForm, MultiImageForm
from .models import ImageAsset, LabelDataset, LabelSchema, Task
from labeling.services import queue as queue_svc


def _can_access(p: Project, user) -> bool:
    return p.is_accessible_by(user)


def _is_admin(p: Project, user) -> bool:
    if user.is_superuser or p.owner_id == user.id:
        return True
    m = p.get_membership(user)
    return m and m.role == ProjectMembership.Role.ADMIN


class LabelingDashboard(LoginRequiredMixin, DetailView):
    model = Project
    template_name = 'labeling/project_dashboard.html'
    context_object_name = 'project'

    def get_object(self, queryset=None):
        p = get_object_or_404(
            Project.objects.select_related('owner').prefetch_related('labeling_datasets', 'label_schemata'),
            pk=self.kwargs['project_id'],
        )
        if not _can_access(p, self.request.user):
            raise Http404()
        return p

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        p = self.object
        from labeling.models import Task as T
        from django.db.models import Count, Q
        ctx['num_tasks'] = T.objects.filter(project=p).count()
        ctx['num_done'] = T.objects.filter(project=p, is_labeled=True).count()
        ctx['can_admin'] = _is_admin(p, self.request.user)
        return ctx


class LabelDatasetList(LoginRequiredMixin, ListView):
    model = LabelDataset
    template_name = 'labeling/dataset_list.html'
    context_object_name = 'datasets'

    def get_queryset(self):
        p = get_object_or_404(Project, pk=self.kwargs['project_id'])
        if not _can_access(p, self.request.user):
            raise Http404()
        self.project = p
        return LabelDataset.objects.filter(project=p).order_by('name')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['project'] = self.project
        ctx['can_admin'] = _is_admin(self.project, self.request.user)
        return ctx


class LabelDatasetCreate(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = LabelDataset
    form_class = LabelDatasetForm
    template_name = 'labeling/dataset_form.html'

    def test_func(self):
        p = get_object_or_404(Project, pk=self.kwargs['project_id'])
        return _is_admin(p, self.request.user)

    def form_valid(self, form):
        form.instance.project = get_object_or_404(Project, pk=self.kwargs['project_id'])
        r = super().form_valid(form)
        messages.success(self.request, _('Dataset created.'))
        return r

    def get_success_url(self):
        return reverse('labeling:dataset_list', kwargs={'project_id': self.kwargs['project_id']})


class ImageUpload(LoginRequiredMixin, UserPassesTestMixin, FormView):
    form_class = MultiImageForm
    template_name = 'labeling/dataset_upload.html'

    def test_func(self):
        p = get_object_or_404(Project, pk=self.kwargs['project_id'])
        return _is_admin(p, self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        self.project = get_object_or_404(Project, pk=self.kwargs['project_id'])
        self.dataset = get_object_or_404(
            LabelDataset, pk=self.kwargs['dataset_id'], project=self.project
        )
        ctx['project'] = self.project
        ctx['dataset'] = self.dataset
        return ctx

    def form_valid(self, form):
        self.project = get_object_or_404(Project, pk=self.kwargs['project_id'])
        self.dataset = get_object_or_404(
            LabelDataset, pk=self.kwargs['dataset_id'], project=self.project
        )
        files = self.request.FILES.getlist('file')
        if not files:
            form.add_error(None, _('Choose at least one file.'))
            return self.form_invalid(form)
        for f in files:
            ImageAsset.objects.create(dataset=self.dataset, file=f)
        messages.success(self.request, _('Images uploaded.'))
        return redirect('labeling:map', project_id=self.project.id)


class MapView(LoginRequiredMixin, TemplateView):
    template_name = 'labeling/map.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        p = get_object_or_404(Project, pk=self.kwargs['project_id'])
        if not _can_access(p, self.request.user):
            raise Http404()
        from labeling.services.exporters import geojson as g
        ctx['project'] = p
        ctx['geojson'] = json.dumps(g.project_images_geojson(p))
        return ctx


class TaskLabel(LoginRequiredMixin, DetailView):
    model = Task
    template_name = 'labeling/task.html'
    context_object_name = 'task'
    pk_url_kwarg = 'task_id'

    def get_object(self, queryset=None):
        t = get_object_or_404(
            Task.objects.select_related('project', 'image', 'schema', 'image__dataset'),
            pk=self.kwargs['task_id'],
        )
        if not t.project.is_accessible_by(self.request.user):
            raise Http404()
        return t

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        t = self.object
        p = t.project
        m = p.get_membership(self.request.user)
        ctx['schema_json'] = json.dumps(t.schema.config or {})
        d = None
        from labeling.models import AnnotationDraft
        try:
            d = AnnotationDraft.objects.get(task=t, user=self.request.user)
        except AnnotationDraft.DoesNotExist:
            pass
        ctx['draft_json'] = json.dumps(d.result if d else [])
        req = self.request
        if t.image and t.image.file and hasattr(t.image.file, 'url'):
            u = req.build_absolute_uri(t.image.file.url) if req else t.image.file.url
        else:
            u = ''
        ctx['image_url'] = u
        ctx['project'] = p
        ctx['can_admin'] = _is_admin(p, self.request.user)
        return ctx


class LabelSchemaEdit(LoginRequiredMixin, UserPassesTestMixin, FormView):
    form_class = LabelSchemaEditForm
    template_name = 'labeling/schema_editor.html'

    def test_func(self):
        p = get_object_or_404(Project, pk=self.kwargs['project_id'])
        return _is_admin(p, self.request.user)

    def get_initial(self):
        p = get_object_or_404(Project, pk=self.kwargs['project_id'])
        sc = p.label_schemata.filter(is_active=True).order_by('-version').first()
        if not sc:
            sc = LabelSchema.objects.create(
                project=p, version=1, config=LabelSchema.default_config(), is_active=True
            )
        self._schema = sc
        return {
            'config_text': json.dumps(sc.config, indent=2, ensure_ascii=False),
            'is_active': sc.is_active,
        }

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['project'] = get_object_or_404(Project, pk=self.kwargs['project_id'])
        return ctx

    def form_valid(self, form):
        p = get_object_or_404(Project, pk=self.kwargs['project_id'])
        sc = getattr(self, '_schema', None) or p.label_schemata.filter(
            is_active=True
        ).order_by('-version').first()
        if not sc:
            sc = LabelSchema.objects.create(
                project=p, version=1, config=LabelSchema.default_config(), is_active=True
            )
        try:
            c = json.loads(form.cleaned_data['config_text'])
        except (json.JSONDecodeError, TypeError):
            form.add_error('config_text', _('Invalid JSON'))
            return self.form_invalid(form)
        if isinstance(c, list):
            c = {
                'tools': ['classification', 'rect', 'polygon', 'point'],
                'labels': c,
            }
        sc.config = c
        sc.is_active = form.cleaned_data.get('is_active', True)
        sc.save()
        messages.success(self.request, _('Schema saved.'))
        return redirect('labeling:dashboard', project_id=p.id)


class NextTaskRedirect(LoginRequiredMixin, TemplateView):
    """GET /labeling/.../next/ -> redirect to first available task page."""

    def get(self, request, *args, **kwargs):
        p = get_object_or_404(Project, pk=kwargs['project_id'])
        if not p.is_accessible_by(request.user):
            raise Http404()
        t = queue_svc.get_next_task_for(request.user, p)
        if t:
            return redirect('labeling:task', project_id=p.id, task_id=t.id)
        messages.info(request, _('No tasks available to label right now.'))
        return redirect('labeling:dashboard', project_id=p.id)


class ReviewList(LoginRequiredMixin, ListView):
    model = Task
    template_name = 'labeling/review.html'
    context_object_name = 'tasks'

    def get_queryset(self):
        p = get_object_or_404(Project, pk=self.kwargs['project_id'])
        u = self.request.user
        m = p.get_membership(u)
        is_rev = m and m.role in (
            ProjectMembership.Role.REVIEWER,
            ProjectMembership.Role.ADMIN,
        )
        is_owner = p.owner_id == u.id
        if not p.is_accessible_by(u) or not (u.is_superuser or is_owner or is_rev):
            raise Http404()
        from labeling.models import Annotation
        return (
            Task.objects.filter(project=p, annotations__status=Annotation.Status.SUBMITTED)
            .select_related('image')
            .distinct()
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['project'] = get_object_or_404(Project, pk=self.kwargs['project_id'])
        return ctx
