from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Annotation, AnnotationDraft, ImageAsset, LabelDataset, LabelSchema, Task, TaskLock


@admin.register(LabelDataset)
class LabelDatasetAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'project', 'created_at']
    list_filter = ['project']
    search_fields = ['name', 'description']


@admin.register(LabelSchema)
class LabelSchemaAdmin(admin.ModelAdmin):
    list_display = ['id', 'project', 'is_active', 'selected_for_labeling', 'created_at']
    list_filter = ['is_active', 'selected_for_labeling', 'project']


class ImageAssetInline(admin.TabularInline):
    model = ImageAsset
    extra = 0
    raw_id_fields = []


@admin.register(ImageAsset)
class ImageAssetAdmin(admin.ModelAdmin):
    list_display = ['id', 'dataset', 'width', 'height', 'has_location', 'created_at']
    list_filter = ['dataset__project']

    @admin.display(boolean=True, description=_('Location'))
    def has_location(self, obj):
        return bool(obj.location)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['id', 'project', 'inner_id', 'is_labeled', 'total_annotations', 'overlap', 'image']
    list_filter = ['is_labeled', 'project']


@admin.register(Annotation)
class AnnotationAdmin(admin.ModelAdmin):
    list_display = ['id', 'task', 'completed_by', 'status', 'was_cancelled', 'created_at']


@admin.register(AnnotationDraft)
class AnnotationDraftAdmin(admin.ModelAdmin):
    list_display = ['id', 'task', 'user', 'updated_at']


@admin.register(TaskLock)
class TaskLockAdmin(admin.ModelAdmin):
    list_display = ['id', 'task', 'user', 'expire_at']
