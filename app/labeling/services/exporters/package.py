from __future__ import annotations

import json
from io import StringIO
from zipfile import ZipFile

from labeling.models import Annotation, ImageAsset, Task
from labeling.services.exporters import coco as coco_exp
from labeling.services.exporters import yolo as yolo_exp


def build_export_zip(project, zf: ZipFile, include: list[str]) -> None:
    """Write selected formats into a zipfile (names lowercase)."""
    if 'geojson' in include:
        from labeling.services.exporters import geojson
        g = geojson.project_images_geojson(project)
        zf.writestr('geo/images.geojson', json.dumps(g, indent=2))
    tasks = list(
        Task.objects.filter(project=project).select_related('image', 'schema', 'image__dataset')
    )
    ann_by_task: dict[int, list] = {}
    for t in tasks:
        ann_by_task[t.id] = list(
            Annotation.objects.filter(task=t, was_cancelled=False)
        )
    if 'yolo' in include:
        for t in tasks:
            anns = [a for a in ann_by_task.get(t.id, []) if not a.was_cancelled]
            if not anns:
                continue
            ann = max(anns, key=lambda a: a.id)
            img = t.image
            labels = t.schema.config.get('labels', [])
            text = yolo_exp.result_to_yolo_text(ann.result or [], labels, img.width, img.height)
            stem = (img.file.name or str(img.id)).rsplit('/', 1)[-1]
            if '.' in stem:
                stem = stem.rsplit('.', 1)[0]
            zf.writestr(f'yolo/labels/{stem}.txt', text)
    if 'coco' in include:
        pairs = []
        for t in tasks:
            pairs.append((t, ann_by_task.get(t.id, [])))
        c = coco_exp.build_coco(project.id, pairs)
        zf.writestr('coco/annotations.json', json.dumps(c, indent=2))
