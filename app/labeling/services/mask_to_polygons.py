"""
Convert raster segmentation masks to normalized polygon regions for Annotation.result.

Polygon-first policy: see docs/10-segmentation-import.md.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any, BinaryIO

import cv2
import numpy as np
from PIL import Image

# Minimum normalized area (fraction of image) to keep a contour
DEFAULT_MIN_REL_AREA = 1e-5


def load_mask_as_class_ids(
    source: str | Path | bytes | BinaryIO,
) -> tuple[np.ndarray, tuple[int, int]]:
    """Load mask as 2D uint32 class ids (H, W). Shape is (height, width)."""
    if isinstance(source, (str, Path)):
        with Path(source).open('rb') as f:
            data = f.read()
    elif isinstance(source, bytes):
        data = source
    else:
        data = source.read()

    im = Image.open(BytesIO(data))
    im.load()
    if im.mode in ('I', 'I;16', 'I;16L', 'I;16B'):
        arr = np.array(im, dtype=np.uint32)
    elif im.mode == 'P':
        arr = np.array(im, dtype=np.uint32)
    elif im.mode == 'L':
        arr = np.array(im, dtype=np.uint32)
    elif im.mode in ('RGB', 'RGBA'):
        # Use first channel only; document multi-channel in doc
        arr = np.array(im.convert('RGB'))[:, :, 0].astype(np.uint32)
    else:
        arr = np.array(im.convert('L'), dtype=np.uint32)
    h, w = arr.shape[:2]
    return arr, (w, h)


def mask_array_to_polygon_regions(
    mask_arr: np.ndarray,
    image_w: int,
    image_h: int,
    pixel_class_to_label_id: dict[int, str],
    *,
    background_values: frozenset[int] | None = None,
    min_relative_area: float = DEFAULT_MIN_REL_AREA,
    epsilon_frac: float = 0.001,
) -> list[dict[str, Any]]:
    """
    Vectorize mask into polygon result items (normalized 0..1 coordinates).

    ``pixel_class_to_label_id`` maps pixel integer (class id) to schema label_id string.
    """
    if mask_arr.ndim != 2:
        raise ValueError('mask must be 2-d')
    mh, mw = mask_arr.shape[:2]
    if (mw, mh) != (image_w, image_h):
        mask_arr = cv2.resize(
            mask_arr.astype(np.float32),
            (image_w, image_h),
            interpolation=cv2.INTER_NEAREST,
        ).astype(np.uint32)

    bg = background_values if background_values is not None else frozenset({0})
    regions: list[dict[str, Any]] = []
    img_area = float(image_w * image_h)
    min_px = max(1.0, min_relative_area * img_area)

    present = np.unique(mask_arr)
    for val in present:
        v = int(val)
        if v in bg:
            continue
        label_id = pixel_class_to_label_id.get(v)
        if not label_id:
            continue
        binary = np.where(mask_arr == val, 255, 0).astype(np.uint8)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            if cv2.contourArea(cnt) < min_px:
                continue
            if len(cnt) < 3:
                continue
            peri = cv2.arcLength(cnt, True)
            eps = max(1e-4, epsilon_frac * peri)
            approx = cv2.approxPolyDP(cnt, eps, closed=True)
            pts = approx.squeeze(1)
            if pts.ndim != 2 or pts.shape[0] < 3:
                pts = cnt.squeeze(1)
            if pts.ndim != 2 or pts.shape[0] < 3:
                continue
            norm_points = [[float(px) / image_w, float(py) / image_h] for px, py in pts]
            regions.append(
                {
                    'type': 'polygon',
                    'label_id': label_id,
                    'points': norm_points,
                    '_source': 'mask_import',
                }
            )
    return regions


def parse_mapping_json(raw: dict[str, Any]) -> dict[int, str]:
    """Map JSON object keys (pixel class as string or int) to label_id."""
    out: dict[int, str] = {}
    for k, v in raw.items():
        try:
            ki = int(k)
        except (TypeError, ValueError):
            continue
        if isinstance(v, str) and v.strip():
            out[ki] = v.strip()
        elif v is not None:
            out[ki] = str(v).strip()
    return out
