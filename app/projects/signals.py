from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Project, ensure_owner_membership


@receiver(post_save, sender=Project)
def project_sync_owner_membership(sender, instance, **kwargs):
    if instance.owner_id:
        ensure_owner_membership(instance)
