from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver

from .models import Annotation, ImageAsset, Task


@receiver(post_delete, sender=ImageAsset)
def on_imageasset_delete(sender, instance, **kwargs):
    if instance.file:
        instance.file.delete(save=False)
    if instance.thumbnail:
        instance.thumbnail.delete(save=False)


@receiver(post_save, sender=Annotation)
@receiver(post_delete, sender=Annotation)
def on_annotation_change(sender, instance, **kwargs):
    task = instance.task
    if task:
        task.recompute_state()


@receiver(pre_delete, sender=Task)
def on_task_pre_delete(sender, instance, **kwargs):
    for lock in list(instance.locks.all()):
        lock.delete()
