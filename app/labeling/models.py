from django.conf import settings
from django.db import models
from django.contrib.gis.db import models as gis_models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


class LabelDataset(models.Model):
    """Logical group of images within a project (labeling datasets)."""
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='labeling_datasets',
        verbose_name=_('Project'),
    )
    name = models.CharField(max_length=200, verbose_name=_('Name'))
    description = models.TextField(blank=True, verbose_name=_('Description'))
    assigned_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='assigned_label_datasets',
        blank=True,
        verbose_name=_('Assigned users'),
        help_text=_(
            'If empty along with groups, all project labelers may work on this dataset. '
            'Otherwise only listed users (or members of assigned groups) see these tasks.'
        ),
    )
    assigned_groups = models.ManyToManyField(
        'auth.Group',
        related_name='assigned_label_datasets',
        blank=True,
        verbose_name=_('Assigned groups'),
        help_text=_('Site-wide Django groups; members may label this dataset when restrictions apply.'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = _('Label dataset')
        verbose_name_plural = _('Label datasets')
        unique_together = [('project', 'name')]

    def __str__(self):
        return f'{self.project.title}: {self.name}'


class LabelSchema(models.Model):
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='label_schemata',
        verbose_name=_('Project'),
    )
    config = models.JSONField(default=dict, blank=True, verbose_name=_('Configuration'))
    is_active = models.BooleanField(default=True, db_index=True, verbose_name=_('Active'))
    selected_for_labeling = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name=_('Show in labeling sidebar'),
        help_text=_('If enabled, this schema appears in the project labeling list and sidebar.'),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-id']
        verbose_name = _('Label schema')
        verbose_name_plural = _('Label schemata')
        constraints = [
            models.UniqueConstraint(fields=['project'], name='labeling_labelschema_project_uniq'),
        ]

    def __str__(self):
        return f'{self.project_id}: label schema #{self.pk}'

    @staticmethod
    def default_config():
        return {
            'tools': ['classification', 'rect', 'polygon', 'point'],
            'labels': [
                {
                    'id': 'ex1',
                    'name': 'Example',
                    'color': '#e74c3c',
                    'hotkey': '1',
                }
            ],
            'allow_empty': True,
            'multi_label': False,
        }


def image_upload_to(instance, filename):
    return f'labeling/images/{instance.dataset_id or "u"}/{timezone.now().strftime("%Y/%m")}/{filename}'


def thumb_upload_to(instance, filename):
    return f'labeling/thumbs/{instance.dataset_id or "u"}/{timezone.now().strftime("%Y/%m")}/{filename}'


class ImageAsset(models.Model):
    dataset = models.ForeignKey(
        LabelDataset,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name=_('Dataset'),
    )
    file = models.ImageField(
        upload_to=image_upload_to,
        max_length=512,
        verbose_name=_('File'),
    )
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    location = gis_models.PointField(
        srid=4326,
        geography=False,
        null=True,
        blank=True,
        spatial_index=True,
        verbose_name=_('Location (WGS84)'),
    )
    captured_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Captured at'))
    exif = models.JSONField(default=dict, blank=True)
    checksum = models.CharField(max_length=64, blank=True, db_index=True)
    thumbnail = models.ImageField(upload_to=thumb_upload_to, max_length=512, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Image')
        verbose_name_plural = _('Images')
        indexes = [
            models.Index(fields=['dataset', 'created_at']),
        ]

    def __str__(self):
        return self.file.name

    @property
    def project_id_from_dataset(self):
        return self.dataset.project_id

    def save(self, *args, **kwargs):
        first = self.pk is None
        super().save(*args, **kwargs)
        if not self.file:
            return
        if (first or not self.checksum) and self.width == 0:
            from .services import images as image_services

            image_services.populate_from_upload(self, save=True)
        if not self.thumbnail and self.width:
            from .services import images as image_services

            try:
                image_services.generate_thumbnail(self, save=True)
            except Exception:
                pass


class Task(models.Model):
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='label_tasks',
        verbose_name=_('Project'),
    )
    image = models.ForeignKey(
        ImageAsset,
        on_delete=models.PROTECT,
        related_name='tasks',
        verbose_name=_('Image'),
    )
    schema = models.ForeignKey(
        LabelSchema,
        on_delete=models.PROTECT,
        related_name='tasks',
        verbose_name=_('Schema'),
    )
    inner_id = models.BigIntegerField(db_index=True, verbose_name=_('Inner id'))
    overlap = models.PositiveSmallIntegerField(
        default=1,
        verbose_name=_('Required annotations'),
    )
    is_labeled = models.BooleanField(default=False, db_index=True, verbose_name=_('Is done'))
    total_annotations = models.PositiveIntegerField(default=0)
    cancelled_annotations = models.PositiveIntegerField(default=0)
    data = models.JSONField(default=dict, blank=True, verbose_name=_('Extra data'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['project', 'inner_id']
        unique_together = [('project', 'inner_id')]
        indexes = [
            models.Index(fields=['project', 'is_labeled']),
        ]
        verbose_name = _('Label task')
        verbose_name_plural = _('Label tasks')

    def __str__(self):
        return f'{self.project_id}#{self.inner_id}'

    def recompute_state(self, save=True):
        """Recompute is_labeled and total/cancelled from annotations."""
        from django.db.models import Count, Q

        aggr = self.annotations.aggregate(
            n=Count("id", filter=Q(was_cancelled=False)),
            c=Count("id", filter=Q(was_cancelled=True)),
        )
        n = aggr["n"] or 0
        c = aggr["c"] or 0
        self.total_annotations = n
        self.cancelled_annotations = c
        # Done when at least `overlap` non-cancelled annotations exist
        self.is_labeled = n >= self.overlap
        if save:
            self.save(
                update_fields=[
                    "total_annotations",
                    "cancelled_annotations",
                    "is_labeled",
                    "updated_at",
                ]
            )


class Annotation(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = 'submitted', _('Submitted')
        APPROVED = 'approved', _('Approved')
        REJECTED = 'rejected', _('Rejected')
        NEEDS_REVISION = 'needs_revision', _('Needs revision')

    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='annotations',
        verbose_name=_('Task'),
    )
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='label_annotations',
        verbose_name=_('Completed by'),
    )
    result = models.JSONField(default=list, verbose_name=_('Result'))
    was_cancelled = models.BooleanField(default=False, db_index=True)
    ground_truth = models.BooleanField(default=False)
    lead_time = models.FloatField(
        null=True,
        blank=True,
        help_text=_('Seconds from open to submit'),
        verbose_name=_('Lead time'),
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SUBMITTED,
        db_index=True,
    )
    parent_annotation = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='revisions',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Annotation')
        verbose_name_plural = _('Annotations')
        indexes = [
            models.Index(fields=['task', 'status']),
        ]

    def __str__(self):
        return f'Annotation {self.pk} (task {self.task_id})'


class AnnotationDraft(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='drafts',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='label_drafts',
    )
    result = models.JSONField(default=list)
    lead_time = models.FloatField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('task', 'user')]
        verbose_name = _('Annotation draft')
        verbose_name_plural = _('Annotation drafts')

    def __str__(self):
        return f'Draft task={self.task_id} user={self.user_id}'


class TaskLock(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='locks',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    expire_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Task lock')
        verbose_name_plural = _('Task locks')
        unique_together = [('task', 'user')]

    def __str__(self):
        return f'Lock t={self.task_id} u={self.user_id}'

    @property
    def is_active(self):
        return self.expire_at >= timezone.now()
