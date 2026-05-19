import json
import io
import zipfile

from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _, ngettext
from django.views import View
from django.views.generic import CreateView, DetailView, FormView, ListView, TemplateView

from projects.models import Project, ProjectMembership
from .forms import (
    DatasetAssigneesForm,
    LabelDatasetForm,
    LabelEntryFormSet,
    LabelSchemaApplyTemplateForm,
    LabelSchemaEditForm,
    MultiImageForm,
)
from .models import Annotation, ImageAsset, LabelDataset, LabelSchema, Task
from labeling.permissions import can_download_labeling_export
from labeling.services import queue as queue_svc
from labeling.services.exporters import package as export_package
from labeling.services.rich_text import sanitize_labeling_instructions


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
    _dashboard_task_limit = 200

    @staticmethod
    def _materialize_dashboard_tasks(queryset, limit: int):
        tasks = list(
            queryset.select_related('image', 'schema').order_by('is_labeled', 'inner_id')[: limit + 1]
        )
        truncated = len(tasks) > limit
        tasks = tasks[:limit]
        for t in tasks:
            name = ''
            img = t.image if t.image_id else None
            f = getattr(img, 'file', None) if img else None
            if f and getattr(f, 'name', None):
                name = f.name.rsplit('/', 1)[-1]
            t.display_filename = name
        return tasks, truncated

    @staticmethod
    def _team_member_progress_row(p, mu, task_base, tv):
        from django.db.models import Exists, OuterRef

        vis_qs = tv.filter_tasks_for_user(p, mu, task_base)
        visible_total = vis_qs.count()
        has_submission = Annotation.objects.filter(
            task=OuterRef('pk'),
            completed_by=mu,
            was_cancelled=False,
        )
        completed_tasks = vis_qs.filter(Exists(has_submission)).count()
        if visible_total:
            progress_pct = min(100, round(100 * completed_tasks / visible_total))
        else:
            progress_pct = 0
        return {
            'user': mu,
            'submitted': tv.submitted_annotations_count(p, mu),
            'pending': tv.pending_visible_tasks_count(p, mu),
            'visible_total': visible_total,
            'completed_tasks': completed_tasks,
            'progress_pct': progress_pct,
        }

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

        from labeling.services import task_visibility as tv

        u = self.request.user
        task_base = Task.objects.filter(project=p)
        my_tasks_qs = tv.filter_personal_label_tasks(p, u, task_base)

        agg = my_tasks_qs.aggregate(
            total=Count('id'),
            done=Count('id', filter=Q(is_labeled=True)),
        )
        nt = agg['total'] or 0
        nd = agg['done'] or 0
        ctx['num_tasks'] = nt
        ctx['num_done'] = nd
        ctx['my_tasks_progress_pct'] = min(100, round(100 * nd / nt)) if nt else 0
        ctx['labeling_sees_all_tasks'] = tv.user_sees_all_project_tasks(p, u)

        lim = self._dashboard_task_limit
        my_tasks, my_trunc = self._materialize_dashboard_tasks(my_tasks_qs, lim)
        ctx['dashboard_my_tasks'] = my_tasks
        ctx['dashboard_my_tasks_truncated'] = my_trunc

        ctx['show_labeling_team_tasks'] = False
        if u.id == p.owner_id:
            team_tasks_qs = task_base.exclude(pk__in=my_tasks_qs.values('pk'))
            team_total = team_tasks_qs.aggregate(total=Count('id'))['total'] or 0
            if team_total > 0:
                team_tasks, team_trunc = self._materialize_dashboard_tasks(team_tasks_qs, lim)
                ctx['dashboard_team_tasks'] = team_tasks
                ctx['dashboard_team_tasks_truncated'] = team_trunc
                ctx['num_team_tasks'] = team_total
                ctx['show_labeling_team_tasks'] = True

        if ctx['labeling_sees_all_tasks']:
            seen = {p.owner_id}
            member_users = [p.owner]
            from projects.models import ProjectMembership

            for m in (
                ProjectMembership.objects.filter(project=p)
                .select_related('user')
                .order_by('user__username')
            ):
                if m.user_id not in seen:
                    seen.add(m.user_id)
                    member_users.append(m.user)
            ctx['labeling_team_progress'] = [
                self._team_member_progress_row(p, mu, task_base, tv)
                for mu in member_users
            ]
        else:
            ctx['labeling_team_progress'] = []
        return ctx


class ProjectLabelingExportDownloadView(LoginRequiredMixin, View):
    """
    GET: download project labeling results as ZIP (COCO, YOLO bundles).
    Query ``include`` — comma-separated subset of coco,yolo (default: both).
    """

    def get(self, request, project_id):
        p = get_object_or_404(Project, pk=project_id)
        if not _can_access(p, request.user):
            raise Http404()
        if not can_download_labeling_export(request.user, p):
            return HttpResponseForbidden()
        raw = request.GET.get('include') or 'coco,yolo'
        include = [x.strip() for x in str(raw).split(',') if x.strip()]
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            export_package.build_export_zip(p, zf, include)
            zf.writestr('README.txt', 'ISR Label export. See docs/08-export-formats.md\n')
        buf.seek(0)
        return FileResponse(
            buf,
            as_attachment=True,
            filename=f'project_{project_id}_labeling_export.zip',
            content_type='application/zip',
        )


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

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['project'] = get_object_or_404(Project, pk=self.kwargs['project_id'])
        return ctx

    def get_success_url(self):
        return reverse('projects:project_detail', kwargs={'pk': self.kwargs['project_id']}) + '#label-datasets'


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
        return redirect(
            reverse('projects:project_detail', kwargs={'pk': self.project.id}) + '#label-datasets'
        )


class DatasetCreateLabelTasksView(LoginRequiredMixin, UserPassesTestMixin, View):
    """POST: create label Task rows for images in a dataset that have none yet."""

    http_method_names = ['post']

    def test_func(self):
        p = get_object_or_404(Project, pk=self.kwargs['project_id'])
        return _is_admin(p, self.request.user)

    def post(self, request, project_id, dataset_id):
        p = get_object_or_404(Project, pk=project_id)
        if not _can_access(p, request.user):
            raise Http404()
        ds = get_object_or_404(LabelDataset, pk=dataset_id, project=p)
        n = queue_svc.ensure_tasks_for_dataset(ds)
        if n:
            msg = ngettext(
                'Created %(count)d label task.',
                'Created %(count)d label tasks.',
                n,
            ) % {'count': n}
            messages.success(request, msg)
        else:
            messages.info(
                request,
                _('No new label tasks were needed—all images already have tasks.'),
            )
        return redirect(
            reverse('projects:project_detail', kwargs={'pk': p.pk}) + '#label-datasets'
        )


class DatasetAssigneesUpdate(LoginRequiredMixin, UserPassesTestMixin, FormView):
    template_name = 'labeling/dataset_assignees.html'
    form_class = DatasetAssigneesForm

    def test_func(self):
        p = get_object_or_404(Project, pk=self.kwargs['project_id'])
        return _is_admin(p, self.request.user)

    def dispatch(self, request, *args, **kwargs):
        self.project = get_object_or_404(Project, pk=kwargs['project_id'])
        self.dataset = get_object_or_404(
            LabelDataset, pk=kwargs['dataset_id'], project=self.project
        )
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['project'] = self.project
        kwargs['dataset'] = self.dataset
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['project'] = self.project
        ctx['dataset'] = self.dataset
        return ctx

    def form_valid(self, form):
        self.dataset.assigned_users.set(form.cleaned_data['assigned_users'])
        self.dataset.assigned_groups.set(form.cleaned_data['assigned_groups'])
        messages.success(self.request, _('Dataset assignees updated.'))
        return redirect(
            reverse('projects:project_detail', kwargs={'pk': self.project.pk}) + '#label-datasets'
        )


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
        from labeling.services.task_visibility import user_can_access_task

        if not user_can_access_task(self.request.user, t):
            raise Http404()
        return t

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        t = self.object
        p = t.project
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
        ctx['image_filename'] = ''
        if t.image and t.image.file and getattr(t.image.file, 'name', None):
            ctx['image_filename'] = str(t.image.file.name).split('/')[-1]
        cfg = t.schema.config or {}
        ctx['schema_labels'] = list(cfg.get('labels') or [])
        ctx['schema_tools'] = list(cfg.get('tools') or [])
        ctx['project'] = p
        ctx['can_admin'] = _is_admin(p, self.request.user)
        raw_instr = (t.schema.config or {}).get('instructions') if t.schema.config else None
        ctx['labeling_instructions_html'] = sanitize_labeling_instructions(
            raw_instr if isinstance(raw_instr, str) else ''
        )
        from labeling.services import task_visibility as tv

        task_base = Task.objects.filter(project=p)
        my_tasks_qs = tv.filter_personal_label_tasks(p, self.request.user, task_base)
        agg = my_tasks_qs.aggregate(
            total=Count('id'),
            done=Count('id', filter=Q(is_labeled=True)),
        )
        nt = agg['total'] or 0
        nd = agg['done'] or 0
        ctx['my_labeling_num_tasks'] = nt
        ctx['my_labeling_num_done'] = nd
        ctx['my_labeling_progress_pct'] = min(100, round(100 * nd / nt)) if nt else 0
        return ctx


def _schema_label_preview(config, max_labels=4):
    labels = (config or {}).get('labels') or []
    parts = []
    for item in labels[:max_labels]:
        if isinstance(item, dict) and item.get('name'):
            parts.append(str(item['name']))
    if len(labels) > max_labels:
        parts.append('…')
    return ', '.join(parts)


def _labels_initial_for_formset(config):
    labels = (config or {}).get('labels') or []
    rows = []
    for lab in labels:
        if isinstance(lab, dict):
            rows.append(
                {
                    'label_id': str(lab.get('id', '') or ''),
                    'name': str(lab.get('name', '') or ''),
                    'color': str(lab.get('color', '') or '#e74c3c'),
                    'hotkey': str(lab.get('hotkey', '') or ''),
                }
            )
    if not rows:
        rows.append(
            {
                'label_id': 'obj1',
                'name': 'Object',
                'color': '#e74c3c',
                'hotkey': '1',
            }
        )
    return rows


def _preserve_config_meta(new_cfg: dict, old_cfg: dict | None) -> dict:
    if '_meta' in new_cfg:
        return new_cfg
    meta = (old_cfg or {}).get('_meta')
    if meta:
        return {**new_cfg, '_meta': meta}
    return new_cfg


def _merge_instructions_field(cfg: dict, form: LabelSchemaEditForm) -> None:
    """Apply sanitized instructions from form; remove key when empty."""
    instr = sanitize_labeling_instructions(form.cleaned_data.get('instructions'))
    if instr:
        cfg['instructions'] = instr
    else:
        cfg.pop('instructions', None)


def _label_rows_preview_count(formset, config) -> int:
    """Approximate label count for setup summary (bound formset or saved config)."""
    if formset.is_bound:
        n = 0
        for f in formset.forms:
            prefix = f.add_prefix('name')
            name_val = (f.data.get(prefix) or '').strip()
            if f.data.get(f.add_prefix('DELETE')):
                continue
            if name_val:
                n += 1
        return n
    return len(
        [
            x
            for x in (config or {}).get('labels') or []
            if isinstance(x, dict) and (str(x.get('name') or '')).strip()
        ]
    )


class LabelSchemaList(LoginRequiredMixin, ListView):
    model = LabelSchema
    template_name = 'labeling/schema_list.html'
    context_object_name = 'schemata'

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.project = get_object_or_404(Project, pk=self.kwargs['project_id'])
        if not _can_access(self.project, request.user):
            raise Http404()

    def get_queryset(self):
        return (
            LabelSchema.objects.filter(project=self.project)
            .annotate(num_tasks=Count('tasks'))
            .order_by('-id')
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['project'] = self.project
        ctx['can_admin'] = _is_admin(self.project, self.request.user)
        from labeling.cv_setup_templates import iter_cv_setup_templates

        buckets = defaultdict(list)
        for t in iter_cv_setup_templates():
            buckets[t.category].append(t)
        cat_title = {
            'classification': _('Classification'),
            'detection': _('Object detection'),
            'segmentation': _('Segmentation'),
            'keypoints': _('Keypoints'),
            'mixed': _('Mixed'),
        }
        order = ('classification', 'detection', 'segmentation', 'keypoints', 'mixed')
        ctx['setup_template_groups'] = [
            (cat_title[c], buckets[c]) for c in order if buckets[c]
        ]
        for s in ctx['schemata']:
            s.label_preview = _schema_label_preview(s.config)
            slug = (s.config or {}).get('_meta', {}).get('template_slug')
            if slug:
                from labeling.cv_setup_templates import get_cv_template

                t = get_cv_template(slug)
                s.setup_template_title = t.title if t else None
            else:
                s.setup_template_title = None
        return ctx


class LabelSchemaLegacyRedirect(LoginRequiredMixin, View):
    """Old /schema/ URL now redirects to the schema list."""

    def get(self, request, project_id):
        p = get_object_or_404(Project, pk=project_id)
        if not _can_access(p, request.user):
            raise Http404()
        return redirect('labeling:schema_list', project_id=p.pk)


class LabelSchemaToggleLabeling(LoginRequiredMixin, UserPassesTestMixin, View):
    http_method_names = ['post']

    def test_func(self):
        p = get_object_or_404(Project, pk=self.kwargs['project_id'])
        return _is_admin(p, self.request.user)

    def post(self, request, project_id, schema_pk):
        p = get_object_or_404(Project, pk=project_id)
        sch = get_object_or_404(LabelSchema, pk=schema_pk, project=p)
        sch.selected_for_labeling = not sch.selected_for_labeling
        sch.save(update_fields=['selected_for_labeling'])
        messages.success(request, _('Labeling visibility updated.'))
        return redirect('labeling:schema_list', project_id=p.pk)


class LabelSchemaApplyTemplate(LoginRequiredMixin, UserPassesTestMixin, View):
    """POST: replace project labeling setup from a CV template (admin)."""

    http_method_names = ['post']

    def test_func(self):
        p = get_object_or_404(Project, pk=self.kwargs['project_id'])
        return _is_admin(p, self.request.user)

    def post(self, request, project_id):
        from labeling.cv_setup_templates import build_config_from_template

        p = get_object_or_404(Project, pk=project_id)
        form = LabelSchemaApplyTemplateForm(request.POST)
        if not form.is_valid():
            messages.error(request, _('Could not apply template.'))
            return redirect('labeling:schema_list', project_id=p.pk)
        slug = form.cleaned_data['slug']
        cfg = build_config_from_template(slug)
        if not cfg:
            messages.error(request, _('Unknown template.'))
            return redirect('labeling:schema_list', project_id=p.pk)
        sch, created = LabelSchema.objects.get_or_create(
            project=p,
            defaults={
                'config': cfg,
                'is_active': True,
                'selected_for_labeling': True,
            },
        )
        if not created:
            sch.config = cfg
            sch.is_active = True
            sch.selected_for_labeling = True
            sch.save()
        messages.success(request, _('Labeling setup updated from template.'))
        return redirect('labeling:schema_list', project_id=p.pk)


class LabelSchemaEdit(LoginRequiredMixin, UserPassesTestMixin, View):
    """Guided label/tools editor with optional raw JSON (admin)."""

    template_name = 'labeling/schema_editor.html'

    def test_func(self):
        p = get_object_or_404(Project, pk=self.kwargs['project_id'])
        return _is_admin(p, self.request.user)

    def _get_schema(self, project_id):
        p = get_object_or_404(Project, pk=project_id)
        sc = LabelSchema.objects.filter(project=p).first()
        if not sc:
            sc = LabelSchema.objects.create(
                project=p,
                config=LabelSchema.default_config(),
                is_active=True,
                selected_for_labeling=True,
            )
        return p, sc

    def get(self, request, project_id):
        p, sc = self._get_schema(project_id)
        form = LabelSchemaEditForm(
            initial={
                'tools': (sc.config or {}).get('tools') or [],
                'allow_empty': (sc.config or {}).get('allow_empty', True),
                'multi_label': (sc.config or {}).get('multi_label', False),
                'mask_import_enabled': bool(
                    (sc.config or {}).get('_meta', {}).get('mask_import_enabled')
                ),
                'instructions': (sc.config or {}).get('instructions') or '',
                'config_text': json.dumps(sc.config or {}, indent=2, ensure_ascii=False),
                'is_active': sc.is_active,
                'use_advanced_json': False,
            }
        )
        formset = LabelEntryFormSet(
            initial=_labels_initial_for_formset(sc.config),
            prefix='labels',
        )
        ctx = self._context(p, sc, form, formset)
        return render(request, self.template_name, ctx)

    def post(self, request, project_id):
        p, sc = self._get_schema(project_id)
        form = LabelSchemaEditForm(request.POST)
        formset = LabelEntryFormSet(request.POST, prefix='labels')
        if not form.is_valid():
            ctx = self._context(p, sc, form, formset)
            return render(request, self.template_name, ctx)
        use_adv = form.cleaned_data['use_advanced_json']
        if use_adv:
            raw = (form.cleaned_data.get('config_text') or '').strip()
            if not raw:
                form.add_error('config_text', _('Required when using raw JSON.'))
                ctx = self._context(p, sc, form, formset)
                return render(request, self.template_name, ctx)
            try:
                c = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                form.add_error('config_text', _('Invalid JSON'))
                ctx = self._context(p, sc, form, formset)
                return render(request, self.template_name, ctx)
            if isinstance(c, list):
                c = {
                    'tools': ['classification', 'rect', 'polygon', 'point'],
                    'labels': c,
                }
            c = _preserve_config_meta(c, sc.config)
            meta = dict((c.get('_meta') or {}))
            meta['mask_import_enabled'] = bool(form.cleaned_data.get('mask_import_enabled'))
            c['_meta'] = meta
            _merge_instructions_field(c, form)
            sc.config = c
        else:
            if not formset.is_valid():
                ctx = self._context(p, sc, form, formset)
                return render(request, self.template_name, ctx)
            tools = form.cleaned_data.get('tools') or []
            if not tools:
                form.add_error(None, _('Select at least one tool.'))
                ctx = self._context(p, sc, form, formset)
                return render(request, self.template_name, ctx)
            labels_out = []
            for row in formset.cleaned_data:
                if not row or row.get('DELETE'):
                    continue
                name = (row.get('name') or '').strip()
                if not name:
                    continue
                lid = (row.get('label_id') or '').strip()
                if not lid:
                    lid = name.lower().replace(' ', '_')[:64]
                labels_out.append(
                    {
                        'id': lid,
                        'name': name,
                        'color': (row.get('color') or '#e74c3c').strip(),
                        'hotkey': (row.get('hotkey') or '').strip(),
                    }
                )
            if not labels_out:
                form.add_error(None, _('Add at least one label (name required).'))
                ctx = self._context(p, sc, form, formset)
                return render(request, self.template_name, ctx)
            new_cfg = {
                'tools': list(tools),
                'labels': labels_out,
                'allow_empty': bool(form.cleaned_data.get('allow_empty')),
                'multi_label': bool(form.cleaned_data.get('multi_label')),
            }
            meta = dict((sc.config or {}).get('_meta') or {})
            meta['mask_import_enabled'] = bool(form.cleaned_data.get('mask_import_enabled'))
            new_cfg['_meta'] = meta
            _merge_instructions_field(new_cfg, form)
            sc.config = new_cfg
        sc.is_active = form.cleaned_data.get('is_active', True)
        if sc.is_active:
            LabelSchema.objects.filter(project=p).exclude(pk=sc.pk).update(is_active=False)
        sc.save()
        messages.success(request, _('Labeling setup saved.'))
        return redirect('labeling:schema_list', project_id=p.pk)

    def _context(self, p, sc, form, formset):
        schema_has_tasks = Task.objects.filter(schema=sc).exists()
        schema_has_annotations = Annotation.objects.filter(task__schema=sc).exists()
        from labeling.cv_setup_templates import get_cv_template

        slug = (sc.config or {}).get('_meta', {}).get('template_slug')
        tpl = get_cv_template(slug) if slug else None
        if form.is_bound:
            selected_tools = list(form.data.getlist('tools'))
        else:
            selected_tools = list(form.initial.get('tools') or [])
        return {
            'project': p,
            'schema': sc,
            'form': form,
            'label_formset': formset,
            'schema_has_tasks': schema_has_tasks,
            'schema_has_annotations': schema_has_annotations,
            'setup_template_label': tpl.title if tpl else None,
            'selected_tools': selected_tools,
            'summary_tools_count': len(selected_tools),
            'summary_labels_count': _label_rows_preview_count(formset, sc.config),
            'summary_allow_empty': (
                form.data.get('allow_empty') == 'on'
                if form.is_bound
                else (sc.config or {}).get('allow_empty', True)
            ),
            'summary_multi_label': (
                form.data.get('multi_label') == 'on'
                if form.is_bound
                else (sc.config or {}).get('multi_label', False)
            ),
            'preview_labeling_url': reverse('labeling:next', kwargs={'project_id': p.pk})
            if schema_has_tasks
            else None,
        }


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


class GlobalNextTaskRedirect(LoginRequiredMixin, TemplateView):
    """GET /labeling/next/ -> redirect to the next available task in an accessible project."""

    def get(self, request, *args, **kwargs):
        found = queue_svc.get_next_task_globally(request.user)
        if found:
            p, t = found
            return redirect('labeling:task', project_id=p.id, task_id=t.id)
        messages.info(request, _('No tasks available to label right now.'))
        return redirect('home')


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
