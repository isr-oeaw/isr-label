from __future__ import annotations

from typing import Any


def build_coco(
    project_id: int,
    tasks_with_annos: list[tuple],  # (task, list[Annotation with result])
) -> dict[str, Any]:
    """Build minimal COCO dict: categories from union of label ids, boxes in absolute pixels."""
    from collections import OrderedDict

    categories: "OrderedDict[str, int]" = OrderedDict()
    images = []
    annotations = []
    ann_id = 1
    for task, anns in tasks_with_annos:
        img = task.image
        im_entry = {
            "id": img.id,
            "width": img.width,
            "height": img.height,
            "file_name": img.file.name.split("/")[-1] if img.file else str(img.id),
        }
        images.append(im_entry)
        for ann in anns:
            if ann.was_cancelled:
                continue
            for r in ann.result or []:
                if r.get('type') != 'rect':
                    continue
                lid = r.get('label_id', 'object')
                if lid not in categories:
                    categories[lid] = len(categories) + 1
                cid = categories[lid]
                x = r.get('x', 0) * img.width
                y = r.get('y', 0) * img.height
                bw = r.get('width', 0) * img.width
                bh = r.get('height', 0) * img.height
                annotations.append(
                    {
                        "id": ann_id,
                        "image_id": img.id,
                        "category_id": cid,
                        "bbox": [round(x, 2), round(y, 2), round(bw, 2), round(bh, 2)],
                        "area": round(bw * bh, 2),
                        "iscrowd": 0,
                    }
                )
                ann_id += 1
    cats = [{"id": v, "name": k} for k, v in categories.items()]
    return {
        "info": {"description": f"ISR Label project {project_id}"},
        "licenses": [],
        "images": images,
        "categories": cats,
        "annotations": annotations,
    }
