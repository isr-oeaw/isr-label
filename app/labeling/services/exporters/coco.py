from __future__ import annotations

from typing import Any


def _polygon_area_pixel_ring(xs: list[float], ys: list[float]) -> float:
    """Shoelace formula; closed implicitly."""
    n = len(xs)
    if n < 3 or n != len(ys):
        return 0.0
    s = 0.0
    for i in range(n):
        j = (i + 1) % n
        s += xs[i] * ys[j] - xs[j] * ys[i]
    return abs(s) / 2.0


def _clean_result_item(r: dict) -> dict:
    return {k: v for k, v in r.items() if not k.startswith('_')}


def build_coco(
    project_id: int,
    tasks_with_annos: list[tuple],  # (task, list[Annotation with result])
) -> dict[str, Any]:
    """Build minimal COCO dict: categories from union of label ids; boxes and segmentation from rects/polygons."""
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
                if not isinstance(r, dict):
                    continue
                r = _clean_result_item(r)
                t = r.get('type')
                if t == 'rect':
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
                elif t == 'polygon':
                    pts = r.get('points') or []
                    if len(pts) < 3:
                        continue
                    lid = r.get('label_id', 'object')
                    if lid not in categories:
                        categories[lid] = len(categories) + 1
                    cid = categories[lid]
                    xs = [float(p[0]) * img.width for p in pts]
                    ys = [float(p[1]) * img.height for p in pts]
                    x0, x1 = min(xs), max(xs)
                    y0, y1 = min(ys), max(ys)
                    bw, bh = x1 - x0, y1 - y0
                    flat: list[float] = []
                    for x, y in zip(xs, ys):
                        flat.extend([round(x, 2), round(y, 2)])
                    area = _polygon_area_pixel_ring(xs, ys)
                    annotations.append(
                        {
                            "id": ann_id,
                            "image_id": img.id,
                            "category_id": cid,
                            "bbox": [round(x0, 2), round(y0, 2), round(bw, 2), round(bh, 2)],
                            "segmentation": [flat],
                            "area": round(area, 2),
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
