"""Merge overlapping annotations (simple: majority for classification, mean not implemented)."""
from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from labeling.models import Annotation, Task
from projects.models import Project


class Command(BaseCommand):
    help = 'For each task in a project, if overlap>1 and N annotations exist, write a consensus as ground_truth.'

    def add_arguments(self, parser):
        parser.add_argument('project_id', type=int)

    @transaction.atomic
    def handle(self, *args, **options):
        pid = options['project_id']
        p = Project.objects.get(pk=pid)
        for t in Task.objects.filter(project=p, is_labeled=True):
            anns = list(Annotation.objects.filter(task=t, was_cancelled=False).order_by('id'))
            if len(anns) < t.overlap:
                continue
            choices = []
            for a in anns:
                for r in a.result or []:
                    if r.get('type') == 'choices' and r.get('selected'):
                        for s in r['selected']:
                            choices.append(s)
            if choices:
                c = Counter(choices)
                winner, _n = c.most_common(1)[0]
                from labeling.models import Annotation as A

                A.objects.create(
                    task=t,
                    result=[{'type': 'choices', 'label_id': 'consensus', 'selected': [winner]}],
                    was_cancelled=False,
                    ground_truth=True,
                    lead_time=0.0,
                    status=A.Status.APPROVED,
                    completed_by=None,
                )
        self.stdout.write(self.style.SUCCESS('Done.'))
