from __future__ import annotations

from typing import Any


def _label_id_to_index(schema_labels: list, label_id: str) -> int:
    for i, lab in enumerate(schema_labels):
        if lab.get('id') == label_id:
            return i
    return 0


def result_to_yolo_text(
    result: list[dict[str, Any]], schema_labels: list, img_w: int, img_h: int
) -> str:
    """Generate YOLO text lines: class_id cx cy w h in normalized 0-1 (relative to model input)."""
    lines = []
    h = max(img_h, 1)
    w = max(img_w, 1)
    for r in result:
        if r.get('type') != 'rect' or r.get('was_cancelled'):
            continue
        lid = r.get('label_id') or ''
        idx = _label_id_to_index(schema_labels, lid)
        x, y, bw, bh = r.get('x', 0), r.get('y', 0), r.get('width', 0), r.get('height', 0)
        cx = (x + bw / 2) / 1.0
        cy = (y + bh / 2) / 1.0
        lines.append(f"{idx} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
    return ''.join(lines)
